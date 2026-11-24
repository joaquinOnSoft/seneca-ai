"""
src/seneca/core/api_storage.py – Conversation history backed by the Seneca-AI REST API.

The server stores every message itself while it produces the reply
(``POST /senecaai/v1/chat``, see :mod:`seneca.core.agent`), so this store
only reads and deletes: the history list downloads conversation
summaries, and the messages of a conversation are fetched on demand with
:meth:`ApiConversationStore.ensure_messages`.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from seneca.api.client import ConversationData, SenecaApiClient, SenecaApiError
from seneca.core.conversation import Conversation, Message, Role
from seneca.utils.config import config

logger = logging.getLogger(__name__)

# Maximum page size accepted by the API
_MAX_PAGE_SIZE = 100

_ROLE_FROM_API = {"user": Role.USER, "assistant": Role.ASSISTANT}

# Errors that must never crash the UI: API errors and network failures
STORE_ERRORS = (SenecaApiError, requests.RequestException)


def create_api_client(timeout: float = 10.0, max_retries: int = 1) -> SenecaApiClient:
    """API client configured from ``.env`` (base URL, API key, user)."""
    return SenecaApiClient(
        base_url=config.seneca_api_base_url,
        api_key=config.seneca_ai_api_key,
        user_id=config.seneca_user_id or None,
        timeout=timeout,
        max_retries=max_retries,
        chat_read_timeout=config.chat_read_timeout,
    )


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 string into a naive local datetime (as used by the app)."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone().replace(tzinfo=None)


def conversation_from_api(data: ConversationData) -> Conversation:
    """Convert an API :class:`ConversationData` to a domain :class:`Conversation`."""
    conv = Conversation(id=data.id, title=data.title, stored=True)
    conv.created_at = _parse_datetime(data.created_at)
    conv.messages = [
        Message(
            role=_ROLE_FROM_API[m.role],
            content=m.content,
            timestamp=_parse_datetime(m.timestamp),
        )
        for m in data.messages
    ]
    return conv


class ApiConversationStore:
    """Read and delete the user's conversations through the Seneca-AI REST API.

    All methods log and swallow API/network errors so that a stopped
    API server never breaks the chat UI.
    """

    def __init__(self, client: SenecaApiClient) -> None:
        self._client = client

    @classmethod
    def from_config(cls) -> "ApiConversationStore":
        return cls(create_api_client())

    def load_conversations(self, limit: int = 20) -> list[Conversation]:
        """Return the summaries (without messages) of the *limit* most recent conversations."""
        try:
            summaries = self._client.list_conversations(
                per_page=max(1, min(limit, _MAX_PAGE_SIZE))
            )
        except STORE_ERRORS as exc:
            logger.warning("Could not load conversations from the API: %s", exc)
            return []
        return [conversation_from_api(s) for s in summaries]

    def ensure_messages(self, conv: Conversation) -> None:
        """Download the messages of *conv* if only its summary is loaded."""
        if not conv.stored or conv.messages:
            return
        try:
            full = self._client.get_conversation(conv.id)
        except STORE_ERRORS as exc:
            logger.error("Could not load conversation %s from the API: %s", conv.id, exc)
            return
        conv.messages = conversation_from_api(full).messages

    def delete_conversation(self, conv: Conversation) -> None:
        """Delete *conv* from the server (no-op if it was never stored)."""
        if not conv.stored:
            return
        try:
            self._client.delete_conversation(conv.id)
            conv.stored = False
        except STORE_ERRORS as exc:
            logger.error("Could not delete conversation %s through the API: %s", conv.id, exc)
