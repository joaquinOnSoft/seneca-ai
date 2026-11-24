"""
tests/seneca/core/test_api_storage.py – Unit tests for :class:`ApiConversationStore`.

The :class:`SenecaApiClient` is replaced by a mock, so no API server is needed.
The store only reads and deletes: the server stores the messages itself
while it produces each reply (see tests/seneca/core/test_agent.py).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from seneca.api.client import ConversationData, ConversationMessage, SenecaServerError
from seneca.core.api_storage import ApiConversationStore, conversation_from_api
from seneca.core.conversation import Conversation, Role

SERVER_ID = "6553f1a2b3c4d5e6f7a8b9c0"


def _conv_data(conv_id=SERVER_ID, messages=()):
    return ConversationData(
        id=conv_id,
        user_id="u1",
        title="Hola",
        created_at="2026-01-01T10:00:00Z",
        updated_at="2026-01-01T10:00:00Z",
        messages=list(messages),
    )


@pytest.fixture
def api_client():
    return MagicMock()


@pytest.fixture
def store(api_client):
    return ApiConversationStore(api_client)


def _local_chat(*texts):
    """A conversation that only exists in the app (not stored yet)."""
    conv = Conversation()
    for i, text in enumerate(texts):
        conv.add_message(Role.USER if i % 2 == 0 else Role.ASSISTANT, text)
    return conv


class TestConversions:
    def test_conversation_from_api(self):
        data = _conv_data(messages=[
            ConversationMessage("user", "Hola", "2026-01-01T10:00:00Z"),
            ConversationMessage("assistant", "¡Hola!", "2026-01-01T10:00:02+00:00"),
        ])
        conv = conversation_from_api(data)
        assert conv.id == SERVER_ID
        assert conv.title == "Hola"
        assert conv.stored is True
        assert [m.role for m in conv.messages] == [Role.USER, Role.ASSISTANT]
        # Converted to naive local time, like the datetimes created by the app
        assert conv.created_at.tzinfo is None
        expected = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        assert conv.created_at == expected

    def test_new_local_conversation_is_not_stored(self):
        assert Conversation().stored is False


class TestLoad:
    def test_load_returns_summaries(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        result = store.load_conversations(20)
        assert [c.id for c in result] == [SERVER_ID]
        assert result[0].messages == []
        assert result[0].stored is True
        api_client.list_conversations.assert_called_once_with(per_page=20)

    def test_load_limit_is_clamped_to_api_maximum(self, store, api_client):
        api_client.list_conversations.return_value = []
        store.load_conversations(500)
        api_client.list_conversations.assert_called_once_with(per_page=100)

    def test_load_when_api_is_down_returns_empty_list(self, store, api_client):
        api_client.list_conversations.side_effect = requests.ConnectionError("down")
        assert store.load_conversations() == []

    def test_ensure_messages_downloads_once(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        api_client.get_conversation.return_value = _conv_data(messages=[
            ConversationMessage("user", "Hola", "2026-01-01T10:00:00Z"),
        ])
        conv = store.load_conversations()[0]

        store.ensure_messages(conv)
        store.ensure_messages(conv)

        api_client.get_conversation.assert_called_once_with(SERVER_ID)
        assert [m.content for m in conv.messages] == ["Hola"]

    def test_ensure_messages_ignores_new_local_conversations(self, store, api_client):
        store.ensure_messages(_local_chat("Hola"))
        api_client.get_conversation.assert_not_called()

    def test_ensure_messages_when_api_is_down_does_not_raise(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        api_client.get_conversation.side_effect = SenecaServerError("boom", status_code=500)
        conv = store.load_conversations()[0]
        store.ensure_messages(conv)
        assert conv.messages == []


class TestDelete:
    def test_delete_stored_conversation(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        conv = store.load_conversations()[0]
        store.delete_conversation(conv)
        api_client.delete_conversation.assert_called_once_with(SERVER_ID)
        assert conv.stored is False

    def test_delete_unsaved_conversation_is_noop(self, store, api_client):
        store.delete_conversation(_local_chat("Hola"))
        api_client.delete_conversation.assert_not_called()

    def test_delete_error_does_not_raise(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        api_client.delete_conversation.side_effect = requests.ConnectionError("down")
        conv = store.load_conversations()[0]
        store.delete_conversation(conv)
        assert conv.stored is True
