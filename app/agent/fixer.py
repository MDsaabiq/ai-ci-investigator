import os
from typing import Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from app.models.fix import ProposedFix

load_dotenv()

FIXER_SYSTEM_PROMPT = """
You are an expert CI/CD and software engineer specializing in automated remediation.

Your job is to generate minimal, precise, and correct code changes to fix a diagnosed CI/CD failure.

You will receive:
1. The Root Cause Analysis (RCA) explaining the failure.
2. The relevant repository files and inspection results.

Instructions:
1. Generate the exact, complete file content for each file that needs to be created or modified.
2. Make minimal and surgical changes — do not rewrite unrelated code.
3. Ensure syntax and imports are 100% correct.
4. Return a valid JSON object matching the ProposedFix schema with:
   - "explanation": string explaining the fix
   - "changes": list of objects with "path", "action" ("create", "modify", "delete"), and "content"
"""


class Fixer:
    def __init__(self, model: str | None = None):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")

        selected_model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

        self.llm = ChatGroq(
            model=selected_model,
            temperature=0,
            api_key=api_key,
            max_tokens=1000,
        )

        self.structured_llm = self.llm.with_structured_output(
            ProposedFix,
            method="json_mode",
        )

    def generate_fix(
        self,
        final_rca: dict[str, Any],
        additional_evidence: dict[str, str] | None = None,
        rag_context: str | None = None,
    ) -> ProposedFix:
        additional_text = ""
        if additional_evidence:
            additional_text = "\n\nRepository context and inspected files:\n"
            for name, content in additional_evidence.items():
                additional_text += f"\n--- File: {name} ---\n{content}\n"

        rag_text = ""
        if rag_context:
            rag_text = f"\n\nRelevant Historical Incidents & Standard Fixes (from Knowledge Base):\n{rag_context}\n"

        prompt_text = f"""
Here is the diagnosed Root Cause Analysis (RCA):
Hypothesis: {final_rca.get('hypothesis')}
Evidence: {final_rca.get('evidence')}
Inspected Files: {final_rca.get('inspected_files')}
{additional_text}
{rag_text}

Generate a valid JSON object matching the ProposedFix schema containing the exact, minimal code changes needed to fix this failure.
"""

        response = self.structured_llm.invoke(
            [
                ("system", FIXER_SYSTEM_PROMPT),
                ("human", prompt_text),
            ]
        )

        return response
