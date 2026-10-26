import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores.azuresearch import AzureSearch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

INCIDENTS_PATH = Path(__file__).parent.parent.parent / "data" / "incidents.json"
CHROMA_PERSIST_DIR = str(Path(__file__).parent.parent.parent / "data" / "chroma_db")


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


def get_chroma_store(chunks: list[Document] | None = None):
    """Initializes ChromaDB vector store (fallback for deprovisioned Azure AI Search)."""
    from langchain_chroma import Chroma

    if chunks:
        return Chroma.from_documents(
            documents=chunks,
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name="ci-incidents",
        )

    store = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name="ci-incidents",
    )
    if store._collection.count() == 0:
        docs = load_incident_documents()
        doc_chunks = chunk_documents(docs)
        if doc_chunks:
            store.add_documents(doc_chunks)
    return store


def get_embeddings():
    """3. Embeddings: Initializes Azure OpenAI text embeddings if endpoint & key are configured."""
    raw_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not raw_endpoint or not api_key:
        return None

    try:
        clean_endpoint = raw_endpoint.replace("/openai/v1/", "").replace("/openai/v1", "").replace("/openai", "").rstrip("/")
        deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
        api_version = os.getenv("AZURE_OPENAI_API_EMBEDDING_VERSION") or "2024-02-01"

        return AzureOpenAIEmbeddings(
            azure_endpoint=clean_endpoint,
            api_key=api_key,
            azure_deployment=deployment,
            api_version=api_version,
        )
    except Exception as e:
        print(f"⚠️ Azure OpenAI Embeddings initialization failed: {e}")
        return None


def store_embeddings(chunks: list[Document], embeddings=None):
    """4. Store Embeddings: Uploads chunks to Azure AI Search, or falls back to ChromaDB."""
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "ci-incidents")

    if search_endpoint and search_key and embeddings:
        try:
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
        except Exception as e:
            print(f"⚠️ Azure AI Search failed ({e}). Falling back to ChromaDB.", flush=True)

    print("💡 Using ChromaDB vector store...", flush=True)
    return get_chroma_store(chunks)


_azure_status_cache = None


def check_azure_status(force_refresh: bool = False) -> dict:
    """Checks whether Azure AI Search and Azure OpenAI Embeddings are functional."""
    global _azure_status_cache
    if _azure_status_cache is not None and not force_refresh:
        return _azure_status_cache

    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    raw_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not (search_endpoint and search_key and raw_endpoint and api_key):
        _azure_status_cache = {
            "azure_working": False,
            "provider": "ChromaDB",
            "reason": "Azure credentials not configured",
        }
        return _azure_status_cache

    try:
        embeddings = get_embeddings()
        if not embeddings:
            _azure_status_cache = {
                "azure_working": False,
                "provider": "ChromaDB",
                "reason": "Azure OpenAI Embeddings configuration failed",
            }
            return _azure_status_cache

        # Test embedding probe
        embeddings.embed_query("ping")

        # Test search connectivity
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "ci-incidents")
        vector_store = AzureSearch(
            azure_search_endpoint=search_endpoint,
            azure_search_key=search_key,
            index_name=index_name,
            embedding_function=embeddings.embed_query,
        )
        vector_store.similarity_search("ping", k=1)

        _azure_status_cache = {
            "azure_working": True,
            "provider": "Azure AI Search",
        }
    except Exception as e:
        _azure_status_cache = {
            "azure_working": False,
            "provider": "ChromaDB",
            "reason": str(e),
        }

    return _azure_status_cache


def get_vector_store():
    """Connects to the vector store (Azure AI Search or ChromaDB fallback)."""
    status = check_azure_status()
    if status.get("azure_working"):
        search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        search_key = os.getenv("AZURE_SEARCH_API_KEY")
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "ci-incidents")
        embeddings = get_embeddings()
        return AzureSearch(
            azure_search_endpoint=search_endpoint,
            azure_search_key=search_key,
            index_name=index_name,
            embedding_function=embeddings.embed_query,
        )

    return get_chroma_store()


def ingest_documents() -> dict:
    """Ingestion: loads, chunks, and uploads incidents to vector DB (Azure AI Search or ChromaDB fallback)."""
    global _azure_status_cache
    _azure_status_cache = None  # Reset cache to re-verify during ingestion

    docs = load_incident_documents()
    print(f"Loaded {len(docs)} incidents from {INCIDENTS_PATH.name}.", flush=True)
    chunks = chunk_documents(docs)
    print(f"Split into {len(chunks)} semantic chunks.", flush=True)
    embeddings = get_embeddings()
    vs = store_embeddings(chunks, embeddings)
    provider = "Azure AI Search" if type(vs).__name__ == "AzureSearch" else "ChromaDB"
    return {
        "status": "success",
        "provider": provider,
        "incidents_count": len(docs),
        "chunks_count": len(chunks),
    }


if __name__ == "__main__":
    print(">>> Starting ingestion (Azure AI Search or ChromaDB fallback)...", flush=True)
    result = ingest_documents()
    print(f">>> Result: {result}", flush=True)
    print(">>> Testing search...", flush=True)
    vs = get_vector_store()
    test_results = vs.similarity_search("ModuleNotFoundError", k=1)
    if test_results:
        print(f"🔍 Test Match: {test_results[0].page_content.splitlines()[0]}", flush=True)
    print("🎉 Ingestion and verification complete!", flush=True)
