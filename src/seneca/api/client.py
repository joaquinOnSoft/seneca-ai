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
>>>
>>> # Conversations
>>> conv = client.create_conversation("Saludo", [
...     ConversationMessage("user", "Hola", "2026-01-01T10:00:00+00:00"),
... ])
>>> client.append_messages(conv.id, [
...     ConversationMessage("assistant", "¡Hola!", "2026-01-01T10:00:02+00:00"),
... ])
>>> summaries = client.list_conversations(per_page=20)   # without messages
>>>
>>> # Chat: the server calls the LLM and streams the reply
>>> with client.stream_chat(content="Hola") as stream:
...     for event in stream:
...         if event.event == "token":
...             print(event.data["text"], end="")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Union

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


class SenecaForbiddenError(SenecaApiError):
    """Raised on 403 Forbidden responses."""


class SenecaNotFoundError(SenecaApiError):
    """Raised on 404 Not Found responses."""


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


@dataclass(frozen=True)
class ConversationMessage:
    """A single message of a stored conversation."""

    role: str
    """``"user"`` or ``"assistant"``."""
    content: str
    timestamp: str
    """ISO 8601 timestamp."""

    def to_json(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ConversationMessage":
        return cls(role=data["role"], content=data["content"], timestamp=data["timestamp"])


@dataclass(frozen=True)
class ConversationData:
    """A conversation as returned by the ``/conversations`` endpoints.

    ``messages`` is empty for the summaries returned by
    :meth:`SenecaApiClient.list_conversations` unless
    ``include_messages=True`` was requested.
    """

    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: Optional[str] = None
    messages: List[ConversationMessage] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ConversationData":
        return cls(
            id=data["_id"],
            user_id=data["user_id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
            messages=[ConversationMessage.from_json(m) for m in data.get("messages", [])],
        )


@dataclass(frozen=True)
class ChatCapabilities:
    """LLM used by the server's chat (``/chat/capabilities``)."""

    provider: str
    model: str
    tool_calling: bool


@dataclass(frozen=True)
class ChatEvent:
    """One Server-Sent Event of a streamed chat reply.

    ``event`` is ``conversation``, ``token``, ``tool_calls``, ``done`` or
    ``error``; ``data`` is the decoded JSON payload (see docs/chat-api.md).
    """

    event: str
    data: Dict[str, Any]


class ChatStream:
    """Iterator over the :class:`ChatEvent` objects of a streamed reply.

    Call :meth:`close` (possibly from another thread) to cancel the reply:
    the server notices the closed connection, stops the LLM and stores the
    text generated so far.
    """

    def __init__(self, response: requests.Response) -> None:
        self._response = response
        self._closed = False

    def __iter__(self) -> Iterator[ChatEvent]:
        event, data_lines = "message", []
        try:
            for line in self._response.iter_lines(decode_unicode=True):
                if line is None:
                    continue
                if line == "":
                    # A blank line ends the event
                    if data_lines:
                        yield ChatEvent(event, json.loads("\n".join(data_lines)))
                    event, data_lines = "message", []
                elif line.startswith(":"):
                    continue  # SSE comment (keep-alive)
                elif line.startswith("event:"):
                    event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].lstrip())
        except (requests.RequestException, AttributeError, ValueError, OSError):
            # Closing the response from another thread interrupts the read
            if not self._closed:
                raise
        finally:
            self.close()

    def close(self) -> None:
        """Close the connection (cancels the reply if it is still running)."""
        self._closed = True
        self._response.close()

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self) -> "ChatStream":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_STATUS_EXCEPTION_MAP: Dict[int, type] = {
    400: SenecaBadRequestError,
    401: SenecaAuthenticationError,
    403: SenecaForbiddenError,
    404: SenecaNotFoundError,
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
    user_id:
        Optional user sent via ``X-SENECA-AI-USER-ID`` header, so that
        conversations are stored on behalf of that user when
        authenticating with the API key.
    """

    base_url: str
    api_key: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    chat_read_timeout: float = 300.0
    """Seconds to wait for the next chunk of a streamed chat reply."""
    _session: requests.Session = field(init=False, repr=False)
    _stream_session: requests.Session = field(init=False, repr=False)

    # -- lifecycle -----------------------------------------------------------

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._session = self._build_session()
        # Chat requests are never retried automatically: a retried POST could
        # store the user's message twice
        self._stream_session = requests.Session()

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
        """Close the underlying HTTP sessions."""
        self._session.close()
        self._stream_session.close()

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
        if self.user_id:
            headers["X-SENECA-AI-USER-ID"] = self.user_id
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

    # -- conversations -------------------------------------------------------

    def _conversations_url(self, conversation_id: Optional[str] = None) -> str:
        url = f"{self.base_url}/senecaai/v1/conversations"
        return f"{url}/{conversation_id}" if conversation_id else url

    def list_conversations(
        self,
        *,
        per_page: int = 20,
        page: int = 1,
        include_messages: bool = False,
    ) -> List[ConversationData]:
        """Return a page of the user's conversations, newest first.

        ``GET /senecaai/v1/conversations``

        Parameters
        ----------
        per_page:
            Conversations per page (1-100).
        page:
            1-based page number.
        include_messages:
            When *False* (default) only the summaries are returned and
            :attr:`ConversationData.messages` is empty.

        Raises
        ------
        SenecaBadRequestError
            If the pagination parameters are invalid.
        SenecaApiError
            On any other HTTP error.
        """
        url = self._conversations_url()
        params = {
            "convPerPage": per_page,
            "numPage": page,
            "includeMessages": str(include_messages).lower(),
        }
        logger.debug("GET %s  params=%s", url, params)

        response = self._session.get(
            url, headers=self._headers(), params=params, timeout=self.timeout
        )
        self._raise_for_status(response)
        return [ConversationData.from_json(item) for item in response.json()]

    def get_conversation(self, conversation_id: str) -> ConversationData:
        """Return a conversation including all its messages.

        ``GET /senecaai/v1/conversations/{id}``

        Raises
        ------
        SenecaNotFoundError
            If the conversation does not exist.
        SenecaForbiddenError
            If the conversation belongs to another user.
        """
        url = self._conversations_url(conversation_id)
        logger.debug("GET %s", url)

        response = self._session.get(url, headers=self._headers(), timeout=self.timeout)
        self._raise_for_status(response)
        return ConversationData.from_json(response.json())

    def create_conversation(
        self, title: str, messages: List[ConversationMessage]
    ) -> ConversationData:
        """Create a new conversation and return it (with its server ``id``).

        ``POST /senecaai/v1/conversations``
        """
        url = self._conversations_url()
        logger.debug("POST %s", url)

        response = self._session.post(
            url,
            headers=self._headers(),
            json={"title": title, "messages": [m.to_json() for m in messages]},
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return ConversationData.from_json(response.json())

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: Optional[str] = None,
        messages: Optional[List[ConversationMessage]] = None,
    ) -> ConversationData:
        """Change the title and/or replace all the messages of a conversation.

        ``PATCH /senecaai/v1/conversations/{id}``

        Raises
        ------
        ValueError
            If neither *title* nor *messages* is provided.
        """
        body: Dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if messages is not None:
            body["messages"] = [m.to_json() for m in messages]
        if not body:
            raise ValueError("Provide 'title' and/or 'messages' to update.")

        url = self._conversations_url(conversation_id)
        logger.debug("PATCH %s", url)

        response = self._session.patch(
            url, headers=self._headers(), json=body, timeout=self.timeout
        )
        self._raise_for_status(response)
        return ConversationData.from_json(response.json())

    def append_messages(
        self, conversation_id: str, messages: List[ConversationMessage]
    ) -> ConversationData:
        """Append *messages* at the end of a conversation.

        ``POST /senecaai/v1/conversations/{id}/messages``
        """
        url = f"{self._conversations_url(conversation_id)}/messages"
        logger.debug("POST %s  (%d messages)", url, len(messages))

        response = self._session.post(
            url,
            headers=self._headers(),
            json={"messages": [m.to_json() for m in messages]},
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return ConversationData.from_json(response.json())

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation.

        ``DELETE /senecaai/v1/conversations/{id}``
        """
        url = self._conversations_url(conversation_id)
        logger.debug("DELETE %s", url)

        response = self._session.delete(url, headers=self._headers(), timeout=self.timeout)
        self._raise_for_status(response)

    # -- chat ----------------------------------------------------------------

    def get_chat_capabilities(self) -> ChatCapabilities:
        """Return the LLM provider/model used by the server and whether it supports tools.

        ``GET /senecaai/v1/chat/capabilities``
        """
        url = f"{self.base_url}/senecaai/v1/chat/capabilities"
        logger.debug("GET %s", url)

        response = self._session.get(url, headers=self._headers(), timeout=self.timeout)
        self._raise_for_status(response)
        data = response.json()
        return ChatCapabilities(
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            tool_calling=bool(data.get("tool_calling", False)),
        )

    def stream_chat(
        self,
        *,
        content: Optional[str] = None,
        conversation_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, str]]] = None,
    ) -> ChatStream:
        """Send a user message (or tool results) and stream the reply.

        ``POST /senecaai/v1/chat``

        Parameters
        ----------
        content:
            The user's message. Mutually exclusive with *tool_results*.
        conversation_id:
            Existing conversation; omit it to create a new one (its id
            arrives in the first ``conversation`` event).
        tools:
            Tools the model may call, as ``{"name", "description",
            "parameters"}`` (JSON schema). They are executed by the client.
        tool_results:
            ``[{"tool_call_id", "content"}]`` for every call of the last
            ``tool_calls`` event; requires *conversation_id*.

        Raises
        ------
        SenecaApiError
            (or a subclass) if the server rejects the request before
            streaming starts (400, 401, 403, 404, 409, 503...).
        """
        body: Dict[str, Any] = {}
        if conversation_id:
            body["conversation_id"] = conversation_id
        if content is not None:
            body["content"] = content
        if tool_results is not None:
            body["tool_results"] = tool_results
        if tools:
            body["tools"] = tools

        url = f"{self.base_url}/senecaai/v1/chat"
        logger.debug("POST %s  (conversation=%s)", url, conversation_id)

        headers = self._headers()
        headers["Accept"] = "text/event-stream"
        response = self._stream_session.post(
            url,
            headers=headers,
            json=body,
            stream=True,
            timeout=(self.timeout, self.chat_read_timeout),
        )
        if not response.ok:
            try:
                self._raise_for_status(response)
            finally:
                response.close()
        return ChatStream(response)
