from pydantic import BaseModel


class InvestigationRequest(BaseModel):
    repository: str
    workflow_run_id: int


class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool