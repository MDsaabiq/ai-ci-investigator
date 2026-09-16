import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from app.agent.prompt import INVESTIGATOR_SYSTEM_PROMPT
from app.models.evidence import InitialEvidence
from app.models.rca import InvestigationResult


load_dotenv()


class Investigator:
    def __init__(self, model: str | None = None):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")

        selected_model = model or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

        self.llm = ChatGroq(
            model=selected_model,
            temperature=0,
            api_key=api_key,
        )

        self.structured_llm = self.llm.with_structured_output(
            InvestigationResult
        )



    def investigate(
        self,
        evidence: InitialEvidence,
    ) -> InvestigationResult:

        response = self.structured_llm.invoke(
            [
                ("system", INVESTIGATOR_SYSTEM_PROMPT),
                (
                    "human",
                    f"""
Here is the initial CI/CD evidence:

{evidence.model_dump_json(indent=2)}

Analyze it and return:
- the most likely hypothesis
- evidence supporting it
- repository files you need to inspect
- additional information you need

Do not generate a fix yet.
""",
                ),
            ]
        )

        return response