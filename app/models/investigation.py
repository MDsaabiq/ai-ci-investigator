
import os

from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv

load_dotenv()

class Investigator:
    def __init__(self):
        api_key = os.getenv("MISTRAL_API_KEY")

        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY is not set")

        self.llm = ChatMistralAI(
            model="mistral-small-2603",
            temperature=0,
            api_key=api_key,
        )