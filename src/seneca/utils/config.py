"""
src/seneca/utils/config.py – Environment & runtime configuration loader.

Reads values from the .env file (via python-dotenv) and exposes a
single :class:`AppConfig` dataclass consumed by the rest of the app.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass(frozen=True)
class AppConfig:
    """Immutable snapshot of runtime configuration."""

    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "openai")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    anthropic_model: str = field(
        default_factory=lambda: os.getenv(
            "ANTHROPIC_MODEL", "claude-3-haiku-20240307"
        )
    )
    app_locale: str = field(
        default_factory=lambda: os.getenv("APP_LOCALE", "es_ES")
    )
    max_conversations: int = field(
        default_factory=lambda: int(
            os.getenv("MAX_CONVERSATIONS", "20")
        )
    )


# Singleton – import and use directly
config = AppConfig()
