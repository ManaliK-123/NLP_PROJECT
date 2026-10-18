import os
import json
import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class LLMProvider:
    """
    Unified LLM provider abstraction that works in Local/Demo-First mode
    without requiring API keys, with optional Gemini or Ollama enhancement.
    """
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.provider_mode = "local"
        
        if self.api_key and len(self.api_key) > 5:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                self.provider_mode = "gemini"
                logger.info("Configured Gemini API provider successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}. Falling back to Local NLP.")
                self.provider_mode = "local"
        else:
            logger.info("No Gemini API key provided. Running in Local NLP Heuristic Mode (100% offline).")
            self.provider_mode = "local"

    def get_active_provider_info(self) -> Dict[str, Any]:
        return {
            "mode": self.provider_mode,
            "is_local": self.provider_mode == "local",
            "model_name": "Local Heuristic + Whisper NLP" if self.provider_mode == "local" else f"Google Gemini ({settings.GEMINI_MODEL})",
            "offline_ready": True
        }

    def enhance_summary(self, raw_summary: str, transcript_text: str) -> str:
        """Optionally enhance summary if cloud LLM is enabled, otherwise return raw_summary."""
        if self.provider_mode == "gemini":
            try:
                prompt = (
                    "Summarize the following meeting concisely focusing strictly on deliverables, "
                    "decisions, and upcoming deadlines. Do not hallucinate.\n\n"
                    f"Transcript:\n{transcript_text[:4000]}"
                )
                response = self.gemini_model.generate_content(prompt)
                if response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini summary enhancement failed: {e}. Using local summary.")
        return raw_summary

# Singleton instance
llm_provider = LLMProvider()
