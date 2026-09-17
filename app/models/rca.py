from pydantic import BaseModel


class InvestigationResult(BaseModel):
    hypothesis: str
    evidence: list[str]
    requested_files: list[str]
    requested_information: list[str]
    search_queries: list[str] = []