from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import InvestigationState
from app.graph.nodes import (
    collect_evidence_node,
    investigate_node,
    fetch_file_node,
    search_repo_node,
    final_rca_node,
    retrieve_rag_node,
    generate_fix_node,
    create_pr_node,
)
from app.graph.routing import should_continue_investigation


def build_investigation_graph():
    builder = StateGraph(InvestigationState)

    # 1. Add Nodes
    builder.add_node("collect_evidence", collect_evidence_node)
    builder.add_node("investigate", investigate_node)
    builder.add_node("fetch_file", fetch_file_node)
    builder.add_node("search_repo", search_repo_node)
    builder.add_node("final_rca", final_rca_node)
    builder.add_node("retrieve_rag", retrieve_rag_node)
    builder.add_node("generate_fix", generate_fix_node)
    builder.add_node("create_pr", create_pr_node)

    # 2. Add Edges
    builder.add_edge(START, "collect_evidence")
    builder.add_edge("collect_evidence", "investigate")

    # 3. Conditional tool loop
    builder.add_conditional_edges(
        "investigate",
        should_continue_investigation,
        {
            "fetch_file": "fetch_file",
            "search_repo": "search_repo",
            "final_rca": "final_rca",
        },
    )

    builder.add_edge("fetch_file", "investigate")
    builder.add_edge("search_repo", "investigate")

    # 4. RCA -> RAG Retrieval -> Fix Generation -> PR Creation
    builder.add_edge("final_rca", "retrieve_rag")
    builder.add_edge("retrieve_rag", "generate_fix")
    builder.add_edge("generate_fix", "create_pr")
    builder.add_edge("create_pr", END)

    # 6. Checkpointer + native interrupt before PR creation
    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["create_pr"],
    )


investigation_graph = build_investigation_graph()
