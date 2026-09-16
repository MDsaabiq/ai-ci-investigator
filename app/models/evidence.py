from pydantic import BaseModel
from typing import Any


class ChangedFile(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None


class InitialEvidence(BaseModel):
    repository: str
    run_id: int

    failed_job: str | None = None
    failed_step: str | None = None

    logs: str = ""

    commit_sha: str
    commit_message: str | None = None

    changed_files: list[ChangedFile] = []