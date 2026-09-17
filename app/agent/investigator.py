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
        additional_evidence: dict[str, str] | None = None,
    ) -> InvestigationResult:

        additional_text = ""
        if additional_evidence:
            additional_text = "\n\nAdditional files/evidence gathered so far:\n"
            for name, content in additional_evidence.items():
                additional_text += f"\n--- File: {name} ---\n{content}\n"

        prompt_text = f"""
Here is the CI/CD evidence:

{evidence.model_dump_json(indent=2)}
{additional_text}

Analyze the evidence and return:
- the most likely hypothesis
- evidence supporting it
- repository files you still need to inspect (leave empty [] if you have enough evidence)
- search_queries to search codebase if exact file paths are unknown (leave empty [] if none)
- additional information you need (leave empty [] if none)

Do not generate a fix 

"""

        response = self.structured_llm.invoke(
            [
                ("system", INVESTIGATOR_SYSTEM_PROMPT),
                ("human", prompt_text),
            ]
        )

        return response
