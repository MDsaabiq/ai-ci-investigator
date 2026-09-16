from pydantic import BaseModel

class InvestigationRequest(BaseModel):
    repository: str
    workflow_run_id: int