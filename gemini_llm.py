import google.generativeai as genai
from langchain.llms.base import LLM
from config import Config
from typing import Optional, List

class GeminiLLM(LLM):
    model_name: str = "gemini-1.5-pro-latest"  # Fixed model name
    model: Optional[any] = None

    def __init__(self):
        super().__init__()
        if not Config.gemini_api_key:
            raise ValueError("Gemini API key is not set in Config.")
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the Gemini model."""
        genai.configure(api_key=Config.gemini_api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        try:
            if not self.model:
                raise ValueError("Model not initialized.")
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating text with Gemini: {e}"

    @property
    def _llm_type(self) -> str:
        return "gemini"
