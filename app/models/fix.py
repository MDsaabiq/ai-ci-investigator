from pydantic import BaseModel, Field, field_validator


class FileChange(BaseModel):
    path: str = Field(
        description="Relative path to the file in the repository (e.g. app/__init__.py)"
    )
    action: str = Field(
        default="create",
        description="Action to perform: 'create', 'modify', or 'delete'",
    )
    content: str = Field(
        default="",
        description="The complete content of the file (empty string if action is 'delete' or creating an empty file)",
    )

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: str) -> str:
        v_str = str(v).lower().strip()
        if v_str in ["add", "new", "create"]:
            return "create"
        if v_str in ["edit", "update", "modify", "change"]:
            return "modify"
        if v_str in ["remove", "delete"]:
            return "delete"
        return v_str


class ProposedFix(BaseModel):
    explanation: str = Field(
        description="Summary explanation of the proposed fix and why it resolves the root cause"
    )
    changes: list[FileChange] = Field(
        description="List of exact file changes needed to fix the issue"
    )
