"""Configuration and environment variables loader."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Find project root and load .env file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv(override=True)


class Settings:
    """Application runtime settings and LLM configuration."""

    def __init__(self) -> None:
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.openai_base_url: Optional[str] = os.getenv("OPENAI_BASE_URL")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")

    def validate_llm_config(self) -> tuple[bool, str]:
        """Validate if LLM configuration is sufficiently set.

        Returns:
            tuple[bool, str]: (is_valid, message)
        """
        # If a custom base URL is used (e.g., local Ollama), API key might not be mandatory
        if self.openai_base_url and "localhost" in self.openai_base_url:
            return True, f"Configured for local endpoint: {self.openai_base_url} (Model: {self.llm_model})"

        if not self.openai_api_key or self.openai_api_key.strip() in ("", "your_openai_api_key_here"):
            return False, (
                "OPENAI_API_KEY is not configured in .env.\n"
                "Please add your API key to .env or configure a local LLM endpoint via OPENAI_BASE_URL."
            )

        return True, f"Configured for model: {self.llm_model}"


settings = Settings()
