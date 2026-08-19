"""Configuration and environment variables loader with zero-dependency fallback."""

import os
from pathlib import Path
from typing import Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env_fallback(filepath: Path) -> None:
    """Zero-dependency .env file parser."""
    if not filepath.exists():
        return
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


# Try importing python-dotenv if available, else use built-in fallback parser
try:
    from dotenv import load_dotenv
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    _load_env_fallback(ENV_PATH)


class Settings:
    """Application runtime settings and LLM configuration."""

    def __init__(self) -> None:
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.openai_base_url: Optional[str] = os.getenv("OPENAI_BASE_URL")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")

    def validate_llm_config(self) -> Tuple[bool, str]:
        """Validate if LLM configuration is sufficiently set.

        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        # If a custom base URL is used (e.g., local Ollama), API key is optional
        if self.openai_base_url and "localhost" in self.openai_base_url:
            return True, f"Configured for local endpoint: {self.openai_base_url} (Model: {self.llm_model})"

        if not self.openai_api_key or self.openai_api_key.strip() in ("", "your_openai_api_key_here"):
            return False, (
                "OPENAI_API_KEY is not configured in .env.\n"
                "Operating in offline expert heuristics mode."
            )

        return True, f"Configured for model: {self.llm_model}"


settings = Settings()
