import os
from typing import Any
from dotenv import load_dotenv

from app.agent.investigator import Investigator
from app.agent.fixer import Fixer
from app.github.client import GitHubClient
from app.graph.state import InvestigationState
from app.rag.retriever import get_rag_context
from app.services.evidence import EvidenceCollector


load_dotenv()


def _get_github_client() -> GitHubClient:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return GitHubClient(token)


def collect_evidence_node(state: InvestigationState) -> dict[str, Any]:
    """Node that fetches initial workflow run metadata, jobs, logs, and commit info."""
    github_client = _get_github_client()
    collector = EvidenceCollector(github_client)

    initial_evidence = collector.collect(
        repository=state["repository"],
        run_id=state["run_id"],
    )

    return {
        "initial_evidence": initial_evidence,
        "additional_evidence": state.get("additional_evidence") or {},
        "iteration_count": 0,
        "max_iterations": state.get("max_iterations") or 3,
        "status": "investigating",
    }


def investigate_node(state: InvestigationState) -> dict[str, Any]:
    """Node that runs LLM analysis over collected evidence."""
    investigator = Investigator()

    if not state.get("initial_evidence"):
        raise ValueError("Initial evidence must be collected before investigation")

    result = investigator.investigate(
        evidence=state["initial_evidence"],
        additional_evidence=state.get("additional_evidence", {}),
    )

    return {
        "hypothesis": result.hypothesis,
        "evidence": result.evidence,
        "requested_files": result.requested_files,
        "requested_information": result.requested_information,
        "search_queries": result.search_queries,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def fetch_file_node(state: InvestigationState) -> dict[str, Any]:
    """Node that fetches specific requested repository files from GitHub."""
    github_client = _get_github_client()
    repo = state["repository"]
    ref = (
        state["initial_evidence"].commit_sha
        if state.get("initial_evidence")
        else None
    )

    additional_evidence = dict(state.get("additional_evidence", {}))
    requested = state.get("requested_files", [])

    for file_path in requested:
        clean_path = file_path.strip().lstrip("/")
        if not clean_path or clean_path.endswith("/"):
            continue

        if clean_path in additional_evidence:
            continue

        try:
            content_file = github_client.get_file(repo, clean_path, ref=ref)
            if hasattr(content_file, "decoded_content"):
                file_text = content_file.decoded_content.decode("utf-8", errors="replace")
                additional_evidence[clean_path] = file_text
            elif isinstance(content_file, list):
                # Directory listing
                names = [f.path for f in content_file]
                additional_evidence[clean_path] = "Directory contents:\n" + "\n".join(names)
        except Exception as e:
            additional_evidence[clean_path] = f"Error fetching file {clean_path}: {e}"

    return {
        "additional_evidence": additional_evidence,
        "requested_files": [],
    }


def search_repo_node(state: InvestigationState) -> dict[str, Any]:
    """Node that searches the GitHub repository for queries/symbols."""
    github_client = _get_github_client()
    repo = state["repository"]

    additional_evidence = dict(state.get("additional_evidence", {}))
    queries = state.get("search_queries", [])

    for query in queries:
        clean_query = query.strip()
        if not clean_query:
            continue

        key = f"search: {clean_query}"
        if key in additional_evidence:
            continue

        try:
            results = github_client.search_repository(repo, clean_query)
            if results:
                summary = f"Search '{clean_query}' matched files:\n" + "\n".join(
                    f"- {r['path']}" for r in results[:5]
                )
            else:
                summary = f"Search '{clean_query}' returned no matches."
            additional_evidence[key] = summary
        except Exception as e:
            additional_evidence[key] = f"Error searching {clean_query}: {e}"

    return {
        "additional_evidence": additional_evidence,
        "search_queries": [],
    }


def final_rca_node(state: InvestigationState) -> dict[str, Any]:
    """Node that finalizes Root Cause Analysis (RCA)."""
    return {
        "final_rca": {
            "hypothesis": state.get("hypothesis"),
            "evidence": state.get("evidence", []),
            "inspected_files": list(state.get("additional_evidence", {}).keys()),
            "status": "investigation_completed",
        },
        "status": "rca_completed",
    }


def retrieve_rag_node(state: InvestigationState) -> dict[str, Any]:
    """Node that retrieves matching historical incident fixes via RAG."""
    hypothesis = (state.get("final_rca") or {}).get("hypothesis", "") or state.get("hypothesis", "")
    rag_context = get_rag_context(hypothesis)
    return {
        "rag_context": rag_context,
        "status": "rag_retrieved",
    }


def generate_fix_node(state: InvestigationState) -> dict[str, Any]:
    """Node that generates structured code changes to fix the root cause."""
    if not state.get("final_rca"):
        raise ValueError("Cannot generate fix without final RCA")

    fixer = Fixer()
    proposed_fix = fixer.generate_fix(
        final_rca=state["final_rca"],
        additional_evidence=state.get("additional_evidence", {}),
        rag_context=state.get("rag_context"),
    )

    return {
        "proposed_fix": proposed_fix,
        "status": "fix_generated",
    }


def create_pr_node(state: InvestigationState) -> dict[str, Any]:


    """Node that creates a Git branch, commits the proposed fix files, and opens a GitHub Pull Request."""
    if not state.get("proposed_fix"):
        raise ValueError("Cannot create PR without proposed_fix")

    github_client = _get_github_client()
    repo = state["repository"]
    run_id = state["run_id"]
    base_sha = (
        state["initial_evidence"].commit_sha
        if state.get("initial_evidence")
        else "main"
    )

    fix = state["proposed_fix"]
    branch_name = f"ai-fix/run-{run_id}"

    # 1. Create fix branch
    github_client.create_branch(repo, branch_name, base_sha)

    # 2. Apply the changes
    github_client.apply_file_changes(
        repository=repo,
        branch_name=branch_name,
        changes=fix.changes,
        commit_message=f"AI CI Fix for workflow run #{run_id}",
    )

    # 3. Create Pull Request
    pr_title = f"fix(ci): automated remediation for workflow run #{run_id}"
    pr_body = f"""## 🤖 AI Automated CI Remediation

### 🔍 Root Cause Analysis
{state.get('final_rca', {}).get('hypothesis', 'N/A')}

### 🛠️ Proposed Fix Explanation
{fix.explanation}

### 📝 Modified Files
""" + "\n".join(f"- `{c.path}` ({c.action})" for c in fix.changes) + f"""

---
*Generated automatically by AI CI Investigator for run #{run_id}*
"""

    pr_result = github_client.create_pull_request(
        repository=repo,
        title=pr_title,
        body=pr_body,
        head_branch=branch_name,
        base_branch="main",
    )

    return {
        "branch_name": branch_name,
        "pr_url": pr_result["pr_url"],
        "pr_number": pr_result["pr_number"],
        "status": "pr_created",
    }


 
