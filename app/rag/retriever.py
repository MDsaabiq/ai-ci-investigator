import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.rag.store import get_vector_store


def retrieve_relevant_incidents(query: str, top_k: int = 2) -> list[str]:
    """Queries the vector store for top matching historical incident chunks."""
    if not query:
        return []
    store = get_vector_store()
    try:
        if type(store).__name__ == "AzureSearch" and hasattr(store, "hybrid_search"):
            docs = store.hybrid_search(query, k=top_k)
        else:
            docs = store.similarity_search(query, k=top_k)
    except Exception as e:
        print(f"⚠️ Search error ({e}), falling back to standard similarity search...")
        docs = store.similarity_search(query, k=top_k)
    return [doc.page_content for doc in docs]


def get_rag_context(query: str, top_k: int = 2) -> str:
    """Returns formatted RAG context ready for LLM prompt and UI."""
    matches = retrieve_relevant_incidents(query, top_k=top_k)
    return "\n\n---\n".join(matches) if matches else ""


if __name__ == "__main__":
    test_query = "GitHub Actions failed: ModuleNotFoundError"
    print(f"\n🔍 Testing Vector Search in Azure AI Search for:\n'{test_query}'\n", flush=True)
    result = get_rag_context(test_query)
    print("--- 🎯 Matched Incident Knowledge ---", flush=True)
    print(result, flush=True)
