"""
src/seneca/core/api_storage.py – Conversation store backed by the Seneca-AI REST API.

Conversations are persisted in MongoDB through the ``/conversations``
endpoints.  The history list only downloads conversation summaries;
the messages of a conversation are fetched on demand with
:meth:`ApiConversationStore.ensure_messages`.  Once a conversation is
stored, new turns are sent with the append-messages endpoint so the
whole conversation is never re-uploaded.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

import requests

from seneca.api.client import (
    ConversationData,
    ConversationMessage,
    SenecaApiClient,
    SenecaApiError,
)
from seneca.core.conversation import Conversation, Message, Role
from seneca.utils.config import config

logger = logging.getLogger(__name__)

# Maximum page size accepted by the API
_MAX_PAGE_SIZE = 100

_ROLE_TO_API = {Role.USER: "user", Role.ASSISTANT: "assistant"}
_ROLE_FROM_API = {value: key for key, value in _ROLE_TO_API.items()}

# Errors that must never crash the UI: API errors and network failures
_STORE_ERRORS = (SenecaApiError, requests.RequestException)


def message_to_api(msg: Message) -> ConversationMessage:
    """Convert a domain :class:`Message` to the API representation."""
    # The app uses naive local datetimes; send them with their UTC offset
    timestamp = msg.timestamp if msg.timestamp.tzinfo else msg.timestamp.astimezone()
    return ConversationMessage(
        role=_ROLE_TO_API[msg.role],
        content=msg.content,
        timestamp=timestamp.isoformat(),
    )


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 string into a naive local datetime (as used by the app)."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone().replace(tzinfo=None)


def conversation_from_api(data: ConversationData) -> Conversation:
    """Convert an API :class:`ConversationData` to a domain :class:`Conversation`."""
    conv = Conversation(id=data.id, title=data.title)
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
    """Persist conversations through the Seneca-AI REST API.

    All methods log and swallow API/network errors so that a stopped
    API server never breaks the chat UI.
    """

    def __init__(self, client: SenecaApiClient) -> None:
        self._client = client
        # conversation id -> number of its messages already stored on the
        # server, or None when only the summary has been downloaded
        self._synced: dict[str, int | None] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls) -> "ApiConversationStore":
        client = SenecaApiClient(
            base_url=config.seneca_api_base_url,
            api_key=config.seneca_ai_api_key,
            user_id=config.seneca_user_id or None,
            timeout=10.0,
            max_retries=1,
        )
        return cls(client)

    def load_conversations(self, limit: int = 20) -> list[Conversation]:
        """Return the summaries (without messages) of the *limit* most recent conversations."""
        try:
            summaries = self._client.list_conversations(
                per_page=max(1, min(limit, _MAX_PAGE_SIZE))
            )
        except _STORE_ERRORS as exc:
            logger.warning("Could not load conversations from the API: %s", exc)
            return []

        conversations = [conversation_from_api(s) for s in summaries]
        with self._lock:
            for conv in conversations:
                self._synced[conv.id] = None
        return conversations

    def ensure_messages(self, conv: Conversation) -> None:
        """Download the messages of *conv* if only its summary is loaded."""
        with self._lock:
            if conv.id not in self._synced or self._synced[conv.id] is not None:
                return
            try:
                full = self._client.get_conversation(conv.id)
            except _STORE_ERRORS as exc:
                logger.error("Could not load conversation %s from the API: %s", conv.id, exc)
                return
            conv.messages = conversation_from_api(full).messages
            self._synced[conv.id] = len(conv.messages)

    def save_conversation(self, conv: Conversation) -> None:
        """Create *conv* on the server or append its new messages.

        On creation, ``conv.id`` is replaced with the id assigned by the server.
        """
        with self._lock:
            # Snapshot: the UI thread may add messages while we are sending
            messages = list(conv.messages)
            try:
                if conv.id not in self._synced:
                    created = self._client.create_conversation(
                        conv.derive_title(), [message_to_api(m) for m in messages]
                    )
                    conv.id = created.id
                elif self._synced[conv.id] is None:
                    # Messages were never downloaded: the local copy is the reference
                    self._client.update_conversation(
                        conv.id, messages=[message_to_api(m) for m in messages]
                    )
                else:
                    pending = messages[self._synced[conv.id]:]
                    if pending:
                        self._client.append_messages(
                            conv.id, [message_to_api(m) for m in pending]
                        )
                self._synced[conv.id] = len(messages)
            except _STORE_ERRORS as exc:
                logger.error("Could not save conversation %s through the API: %s", conv.id, exc)

    def delete_conversation(self, conv: Conversation) -> None:
        """Delete *conv* from the server (no-op if it was never stored)."""
        with self._lock:
            if conv.id not in self._synced:
                return
            try:
                self._client.delete_conversation(conv.id)
                del self._synced[conv.id]
            except _STORE_ERRORS as exc:
                logger.error("Could not delete conversation %s through the API: %s", conv.id, exc)
