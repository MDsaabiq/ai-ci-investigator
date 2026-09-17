from app.graph.state import InvestigationState


def should_continue_investigation(state: InvestigationState) -> str:
    """
    Determines whether the investigation loop should fetch specific files,
    run repository search, or transition to final RCA.
    """
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)

    # Prevent infinite loops
    if iteration >= max_iterations:
        return "final_rca"

    requested_files = state.get("requested_files", [])
    search_queries = state.get("search_queries", [])
    additional_evidence = state.get("additional_evidence", {})

    # 1. Check if there are new specific files to fetch
    new_files_needed = [
        f for f in requested_files
        if f.strip().lstrip("/") not in additional_evidence and not f.strip().endswith("/")
    ]
    if new_files_needed:
        return "fetch_file"

    # 2. Check if there are new search queries to execute
    new_searches_needed = [
        q for q in search_queries
        if f"search: {q.strip()}" not in additional_evidence and q.strip()
    ]
    if new_searches_needed:
        return "search_repo"

    # 3. If no more files/searches needed, complete RCA
    return "final_rca"


def route_approval(state: InvestigationState) -> str:
    """
    Routes based on human approval status.
    If approved -> proceed to create_pr.
    Otherwise -> stop at END.
    """
    if state.get("approval_status") == "approved":
        return "create_pr"
    return "reject"


