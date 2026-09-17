import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.azuresearch import AzureSearch

load_dotenv()

INCIDENTS_PATH = Path(__file__).parent.parent.parent / "data" / "incidents.json"


def load_incident_documents(file_path: Path = INCIDENTS_PATH) -> list[Document]:
    """1. Document Loading: Reads historical incidents from data/incidents.json."""
    if not file_path.exists():
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        docs = []
        for item in data:
            incident_id = item.get("incident_id", "UNKNOWN")
            issue = item.get("issue", "")
            fix = item.get("fix", "")

            content = (
                f"Incident ID: {incident_id}\n"
                f"Issue: {issue}\n"
                f"Fix: {fix}"
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata={"source": "incidents.json", "incident_id": incident_id},
                )
            )
        return docs
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []


def chunk_documents(docs: list[Document]) -> list[Document]:
    """2. Text Chunking: Splits documents into semantic chunks."""
    if not docs:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=30,
    )
    return splitter.split_documents(docs)


def get_embeddings() -> AzureOpenAIEmbeddings:
    """3. Embeddings: Initializes Azure OpenAI text embeddings."""
    raw_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    # Strip '/openai/v1' or trailing slashes so Azure SDK constructs the correct URL
    clean_endpoint = raw_endpoint.replace("/openai/v1/", "").replace("/openai/v1", "").replace("/openai", "").rstrip("/")

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    api_version = os.getenv("AZURE_OPENAI_API_EMBEDDING_VERSION") or "2024-02-01"

    return AzureOpenAIEmbeddings(
        azure_endpoint=clean_endpoint,
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
    )


def store_embeddings(chunks: list[Document], embeddings: AzureOpenAIEmbeddings):
    """4. Store Embeddings: Uploads chunks and embeddings to Azure AI Search."""
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "ci-incidents")

    if not search_endpoint or not search_key:
        print("⚠️ Warning: AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_API_KEY not found in .env. Falling back to In-Memory vector store.")
        from langchain_core.vectorstores import InMemoryVectorStore
        return InMemoryVectorStore.from_documents(chunks, embeddings)

    print(f"Connecting to Azure AI Search at: {search_endpoint} (Index: {index_name})...", flush=True)
    vector_store = AzureSearch(
        azure_search_endpoint=search_endpoint,
        azure_search_key=search_key,
        index_name=index_name,
        embedding_function=embeddings.embed_query,
    )

    if chunks:
        print(f"Uploading {len(chunks)} chunks to Azure AI Search index '{index_name}'...", flush=True)
        doc_ids = vector_store.add_documents(documents=chunks)
        print(f"✅ Successfully uploaded {len(doc_ids)} documents to Azure AI Search!", flush=True)

    return vector_store


def get_vector_store():
    """Connects to the vector store (Azure AI Search or in-memory fallback)."""
    embeddings = get_embeddings()
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "ci-incidents")

    if not search_endpoint or not search_key:
        from langchain_core.vectorstores import InMemoryVectorStore
        docs = load_incident_documents()
        chunks = chunk_documents(docs)
        return InMemoryVectorStore.from_documents(chunks, embeddings)

    return AzureSearch(
        azure_search_endpoint=search_endpoint,
        azure_search_key=search_key,
        index_name=index_name,
        embedding_function=embeddings.embed_query,
    )


def ingest_documents():
    """One-time ingestion: loads, chunks, and uploads incidents to vector DB."""
    docs = load_incident_documents()
    print(f"Loaded {len(docs)} incidents from {INCIDENTS_PATH.name}.", flush=True)
    chunks = chunk_documents(docs)
    print(f"Split into {len(chunks)} semantic chunks.", flush=True)
    embeddings = get_embeddings()
    return store_embeddings(chunks, embeddings)


if __name__ == "__main__":
    print(">>> Starting ingestion into Azure AI Search...", flush=True)
    vs = ingest_documents()
    print(">>> Testing immediate search from Azure AI Search...", flush=True)
    test_results = vs.similarity_search("ModuleNotFoundError", k=1)
    if test_results:
        print(f"🔍 Test Match: {test_results[0].page_content.splitlines()[0]}", flush=True)
    print("🎉 Ingestion and verification complete!", flush=True)
