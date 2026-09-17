from app.rag.store import get_vector_store


def retrieve_relevant_incidents(query: str, top_k: int = 2) -> list[str]:
    """Queries the vector store for top matching historical incident chunks."""
    if not query:
        return []
    store = get_vector_store()
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
