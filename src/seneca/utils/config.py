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
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# Allowed values for faster-whisper configuration
_ALLOWED_MODEL_SIZES = {"tiny", "base", "small", "medium", "large-v3"}
_ALLOWED_COMPUTE_TYPES = {"int8", "float16"}


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
    
    # Faster-whisper configuration
    whisper_model_size: str = field(
        default_factory=lambda: os.getenv("WHISPER_MODEL_SIZE", "small")
    )
    whisper_device: str = field(
        default_factory=lambda: os.getenv("WHISPER_DEVICE", "cpu")
    )
    whisper_compute_type: str = field(
        default_factory=lambda: os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    )
    # Hugging Face token.
    # Please set an HF_TOKEN to enable higher rate limits and faster downloads.
    hf_token: str = field(
        default_factory=lambda: os.getenv("HF_TOKEN", "")
    )

    # Seneca API base URL
    seneca_api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "SENECA_API_BASE_URL", "http://localhost:1414"
        )
    )

    # Seneca AI API Key for authentication
    seneca_ai_api_key: str = field(
        default_factory=lambda: os.getenv("SENECA_AI_API_KEY", "")
    )
    seneca_ai_api_key_file: str = field(
        default_factory=lambda: os.getenv("SENECA_AI_API_KEY_FILE", "")
    )

    def __post_init__(self):
        # Basic validation for whisper_model_size
        if self.whisper_model_size not in _ALLOWED_MODEL_SIZES:
            print(f"Warning: Invalid WHISPER_MODEL_SIZE '{self.whisper_model_size}'. Defaulting to 'small'.")
            object.__setattr__(self, 'whisper_model_size', 'small')
        
        # Basic validation for whisper_compute_type
        if self.whisper_compute_type not in _ALLOWED_COMPUTE_TYPES:
            print(f"Warning: Invalid WHISPER_COMPUTE_TYPE '{self.whisper_compute_type}'. Defaulting to 'int8'.")
            object.__setattr__(self, 'whisper_compute_type', 'int8')

        # Read SENECA_AI_API_KEY from file if SENECA_AI_API_KEY_FILE is provided
        if self.seneca_ai_api_key_file and os.path.exists(self.seneca_ai_api_key_file):
            try:
                with open(self.seneca_ai_api_key_file, 'r') as f:
                    secret_value = f.read().strip()
                    object.__setattr__(self, 'seneca_ai_api_key', secret_value)
                print(f"Info: SENECA_AI_API_KEY loaded from file: {self.seneca_ai_api_key_file}")
            except Exception as e:
                print(f"Warning: Could not read SENECA_AI_API_KEY from file {self.seneca_ai_api_key_file}. Error: {e}")


# Singleton – import and use directly
config = AppConfig()