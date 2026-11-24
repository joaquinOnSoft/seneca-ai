"""
src/seneca/utils/config.py – Environment & runtime configuration loader.

Reads values from the .env file (via python-dotenv) and exposes a
single :class:`AppConfig` dataclass consumed by the rest of the app.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from project root (two levels up from this file)
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# Allowed values for faster-whisper configuration
_ALLOWED_FASTER_WHISPER_MODEL_SIZES = {"tiny", "base", "small", "medium", "large-v3"}
_ALLOWED_FASTER_WHISPER_COMPUTE_TYPES = {"int8", "float16"}
_ALLOWED_STT_BACKENDS = {"faster-whisper", "google"}


@dataclass(frozen=True)
class AppConfig:
    """Immutable snapshot of runtime configuration."""

    # LLM used by the API server (seneca.api.chat): openai | ollama | anthropic.
    # The desktop app no longer calls the LLM; it talks to the API.
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama")
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
    # Stored messages sent to the LLM as context (most recent ones)
    chat_history_max_messages: int = field(
        default_factory=lambda: int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "50"))
    )
    # Seconds the desktop app waits for the next chunk of a streamed reply
    # (the first token can take long while Ollama loads the model)
    chat_read_timeout: float = field(
        default_factory=lambda: float(os.getenv("CHAT_READ_TIMEOUT", "300"))
    )
    # Worker threads of the API server. Each streamed chat reply keeps one
    # busy until it ends, so this bounds the concurrent replies.
    api_threads: int = field(
        default_factory=lambda: int(os.getenv("API_THREADS", "16"))
    )


    # STT configuration
    stt_backend: str = field(
        default_factory=lambda: os.getenv("STT_BACKEND", "faster-whisper")
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
    audio_chunk: int = field(
        default_factory=lambda: int(os.getenv("AUDIO_CHUNK", 1024))
    )
    audio_channels: int = field(
        default_factory=lambda: int(os.getenv("AUDIO_CHANNELS", 1))
    )
    audio_rate: int = field(
        default_factory=lambda: int(os.getenv("AUDIO_RATE", 16000)) # 16kHz for Whisper
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
    # User on whose behalf the desktop app stores conversations through the API
    seneca_user_id: str = field(
        default_factory=lambda: os.getenv("SENECA_USER_ID", "")
    )

    # MongoDB URI
    mongodb_uri: str = field(
        default_factory=lambda: os.getenv("MONGODB_URI", "mongodb://localhost:27017/seneca_db")
    )
    # Optional MongoDB credentials (Docker secrets), kept out of the URI.
    # The user is authenticated against the "admin" database, where the
    # official mongo image creates the root user.
    mongodb_username: str = field(
        default_factory=lambda: os.getenv("MONGODB_USERNAME", "")
    )
    mongodb_password: str = field(
        default_factory=lambda: os.getenv("MONGODB_PASSWORD", "")
    )
    mongodb_username_file: str = field(
        default_factory=lambda: os.getenv("MONGO_ROOT_USERNAME_FILE", "")
    )
    mongodb_password_file: str = field(
        default_factory=lambda: os.getenv("MONGO_ROOT_PASSWORD_FILE", "")
    )

    # JWT Configuration
    jwt_secret_key: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "")
    )
    jwt_secret_key_file: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY_FILE", "")
    )
    jwt_access_token_expires_in: int = field(
        default_factory=lambda: int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_IN", "3600")) # 1 hour
    )

    def __post_init__(self):
        # Basic validation for stt_backend
        if self.stt_backend not in _ALLOWED_STT_BACKENDS:            
            logger.warning(f"Invalid STT_BACKEND '{self.stt_backend}'. Defaulting to 'faster-whisper'.")
            object.__setattr__(self, 'stt_backend', 'faster-whisper')

        # Basic validation for whisper_model_size
        if self.whisper_model_size not in _ALLOWED_FASTER_WHISPER_MODEL_SIZES:
            logger.warning(f"Invalid WHISPER_MODEL_SIZE '{self.whisper_model_size}'. Defaulting to 'small'.")
            object.__setattr__(self, 'whisper_model_size', 'small')
        
        # Basic validation for whisper_compute_type
        if self.whisper_compute_type not in _ALLOWED_FASTER_WHISPER_COMPUTE_TYPES:
            logger.warning(f"Invalid WHISPER_COMPUTE_TYPE '{self.whisper_compute_type}'. Defaulting to 'int8'.")
            object.__setattr__(self, 'whisper_compute_type', 'int8')

        # Secrets provided as files (Docker secrets) take precedence over plain variables
        self._load_secret_from_file('seneca_ai_api_key', self.seneca_ai_api_key_file)
        self._load_secret_from_file('jwt_secret_key', self.jwt_secret_key_file)
        self._load_secret_from_file('mongodb_username', self.mongodb_username_file)
        self._load_secret_from_file('mongodb_password', self.mongodb_password_file)

        if not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY (or JWT_SECRET_KEY_FILE) must be set in the environment "
                             "variables or .env file.")

    def _load_secret_from_file(self, attr_name: str, file_path: str) -> None:
        """Overwrite *attr_name* with the content of *file_path*, if the file exists."""
        if not file_path or not os.path.exists(file_path):
            return
        try:
            with open(file_path, 'r') as f:
                object.__setattr__(self, attr_name, f.read().strip())
            logger.info(f"{attr_name.upper()} loaded from file: {file_path}")
        except Exception as e:
            logger.warning(f"Could not read {attr_name.upper()} from file {file_path}. Error: {e}")


# Singleton – import and use directly
config = AppConfig()