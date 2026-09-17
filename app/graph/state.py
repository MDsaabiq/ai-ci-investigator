from typing import TypedDict, Any
from app.models.evidence import InitialEvidence
from app.models.rca import InvestigationResult
from app.models.fix import ProposedFix


class InvestigationState(TypedDict):
    # Inputs
    repository: str
    run_id: int

    # Evidence & Investigation status
    initial_evidence: InitialEvidence | None
    additional_evidence: dict[str, str]

    # Model deductions
    hypothesis: str | None
    evidence: list[str]
    requested_files: list[str]
    requested_information: list[str]
    search_queries: list[str]

    # Iteration controls
    iteration_count: int
    max_iterations: int

    # RAG knowledge
    rag_context: str | None

    # Final outputs
    final_rca: dict | None
    proposed_fix: ProposedFix | None

    # Human review & approval
    approval_status: str | None

    # Git & PR outputs
    branch_name: str | None
    pr_url: str | None
    pr_number: int | None

    status: str

