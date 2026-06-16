"""
src/seneca/api/client.py – HTTP client wrapper for the Seneca-AI REST API.

Provides :class:`SenecaApiClient`, a high-level, typed interface that
encapsulates every endpoint exposed by the Flask application in ``api.py``.

Usage example
-------------
>>> from seneca.api.client import SenecaApiClient
>>> from seneca.utils.config import config
>>>
>>> client = SenecaApiClient(
...     base_url=config.seneca_api_base_url,
...     api_key="my-secret-key",
... )
>>>
>>> # Health check
>>> health = client.health_check()
>>> print(health)                        # {"status": "ok", "model_status": "loaded"}
>>>
>>> # Supported languages
>>> langs = client.get_supported_languages()
>>> print(langs[0])                      # {"code": "en", "name": "english"}
>>>
>>> # Speech-to-Text
>>> result = client.speech_to_text("/path/to/audio.wav", lang="es")
>>> print(result)                        # {"text": "Hola mundo"}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Union

import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------


class SenecaApiError(Exception):
    """Base exception for all Seneca API client errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class SenecaAuthenticationError(SenecaApiError):
    """Raised on 401 Unauthorized responses."""


class SenecaBadRequestError(SenecaApiError):
    """Raised on 400 Bad Request responses."""


class SenecaServiceUnavailableError(SenecaApiError):
    """Raised on 503 Service Unavailable responses."""


class SenecaServerError(SenecaApiError):
    """Raised on 5xx responses (except 503)."""


# ---------------------------------------------------------------------------
# Response data-classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HealthResponse:
    """Typed representation of the ``/health`` endpoint response."""

    status: str
    model_status: str


@dataclass(frozen=True)
class LanguageInfo:
    """A single language supported by the STT service."""

    code: str
    name: str


@dataclass(frozen=True)
class TranscriptionResult:
    """Result returned by the ``/stt`` endpoint."""

    text: str


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_STATUS_EXCEPTION_MAP: Dict[int, type] = {
    400: SenecaBadRequestError,
    401: SenecaAuthenticationError,
    503: SenecaServiceUnavailableError,
}


@dataclass
class SenecaApiClient:
    """High-level wrapper around the Seneca-AI REST API.

    Parameters
    ----------
    base_url:
        Root URL of the API server (e.g. ``http://localhost:1414``).
        A trailing slash is stripped automatically.
    api_key:
        Value sent in the ``X-SENECA-AI-API-KEY`` header on every request
        (except health-check, which does not require authentication).
    timeout:
        Default request timeout in seconds.
    max_retries:
        Number of automatic retries for transient failures (5xx, timeouts).
    correlation_id:
        Optional correlation id sent via ``X-Correlation-ID`` header.
        If *None*, the server will generate one automatically.
    """

    base_url: str
    api_key: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    correlation_id: Optional[str] = None
    _session: requests.Session = field(init=False, repr=False)

    # -- lifecycle -----------------------------------------------------------

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Create a :class:`requests.Session` with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)   # type: ignore[arg-type]  # HTTPAdapter IS-A BaseAdapter; stubs are wrong
        session.mount("https://", adapter)  # type: ignore[arg-type]

        return session

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> "SenecaApiClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    # -- internal helpers ----------------------------------------------------

    def _headers(self, *, include_api_key: bool = True) -> Dict[str, str]:
        """Build the common request headers."""
        headers: Dict[str, str] = {}
        if include_api_key and self.api_key:
            headers["X-SENECA-AI-API-KEY"] = self.api_key
        if self.correlation_id:
            headers["X-Correlation-ID"] = self.correlation_id
        return headers

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        """Map HTTP error codes to typed exceptions."""
        if response.ok:
            return

        try:
            body = response.json()
        except ValueError:
            body = response.text

        error_message = (
            body.get("error", response.reason)
            if isinstance(body, dict)
            else str(body) or response.reason
        )

        exc_class = _STATUS_EXCEPTION_MAP.get(
            response.status_code,
            SenecaServerError if response.status_code >= 500 else SenecaApiError,
        )

        raise exc_class(
            message=error_message,
            status_code=response.status_code,
            response_body=body,
        )

    # -- public API ----------------------------------------------------------

    def health_check(self) -> HealthResponse:
        """Check the health of the API and the Whisper model.

        ``GET /senecaai/v1/health``

        Returns
        -------
        HealthResponse
            A dataclass with ``status`` (``"ok"`` | ``"degraded"``) and
            ``model_status`` (``"loaded"`` | ``"not loaded"``).

        Raises
        ------
        SenecaApiError
            On unexpected HTTP errors.
        """
        url = f"{self.base_url}/senecaai/v1/health"
        logger.debug("GET %s", url)

        response = self._session.get(
            url,
            headers=self._headers(include_api_key=False),
            timeout=self.timeout,
        )
        # Health can return 503 when degraded – we still want the body.
        try:
            data = response.json()
        except ValueError:
            self._raise_for_status(response)
            return HealthResponse(status="unknown", model_status="unknown")

        return HealthResponse(
            status=data.get("status", "unknown"),
            model_status=data.get("model_status", "unknown"),
        )

    def get_supported_languages(self) -> List[LanguageInfo]:
        """Return the list of languages supported by the STT service.

        ``GET /senecaai/v1/stt/languages``

        Returns
        -------
        list[LanguageInfo]
            Each element contains a ``code`` (e.g. ``"en"``) and a
            ``name`` (e.g. ``"english"``).

        Raises
        ------
        SenecaAuthenticationError
            If the API key is missing or invalid.
        SenecaApiError
            On any other HTTP error.
        """
        url = f"{self.base_url}/senecaai/v1/stt/languages"
        logger.debug("GET %s", url)

        response = self._session.get(
            url,
            headers=self._headers(),
            timeout=self.timeout,
        )
        self._raise_for_status(response)

        return [
            LanguageInfo(code=item["code"], name=item["name"])
            for item in response.json()
        ]

    def speech_to_text(
        self,
        audio: Union[str, Path, BinaryIO],
        *,
        lang: str = "en",
        filename: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file to text via the STT endpoint.

        ``POST /senecaai/v1/stt``

        Parameters
        ----------
        audio:
            Path to a ``.wav`` or ``.mp3`` file **or** an already-opened
            binary file-like object.
        lang:
            BCP-47 language code (e.g. ``"en"``, ``"es"``).  Only the
            primary subtag is used by the server.
        filename:
            Explicit filename to send to the server.  Required when
            *audio* is a file-like object without a ``name`` attribute.

        Returns
        -------
        TranscriptionResult
            A dataclass with a single ``text`` attribute holding the
            transcription.

        Raises
        ------
        FileNotFoundError
            If *audio* is a path that does not exist.
        ValueError
            If the filename cannot be determined.
        SenecaBadRequestError
            If the server rejects the request (missing file, wrong format …).
        SenecaAuthenticationError
            If the API key is missing or invalid.
        SenecaServiceUnavailableError
            If the Whisper model is not loaded on the server.
        SenecaServerError
            On internal server errors.
        """
        url = f"{self.base_url}/senecaai/v1/stt"
        logger.debug("POST %s  lang=%s", url, lang)

        # Resolve the file to send ----------------------------------------
        if isinstance(audio, (str, Path)):
            audio_path = Path(audio)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            resolved_filename = filename or audio_path.name
            file_handle: BinaryIO = open(audio_path, "rb")  # noqa: SIM115
            should_close = True
        else:
            file_handle = audio
            resolved_filename = filename or getattr(file_handle, "name", None)
            if resolved_filename is None:
                raise ValueError(
                    "Cannot determine filename. Pass 'filename' explicitly "
                    "when providing a file-like object without a 'name' attribute."
                )
            # Ensure we only keep the basename
            resolved_filename = Path(resolved_filename).name
            should_close = False

        try:
            files = {"file": (resolved_filename, file_handle)}
            data = {"lang": lang}

            response = self._session.post(
                url,
                headers=self._headers(),
                files=files,
                data=data,
                timeout=self.timeout,
            )
        finally:
            if should_close:
                file_handle.close()

        self._raise_for_status(response)
        return TranscriptionResult(text=response.json()["text"])
