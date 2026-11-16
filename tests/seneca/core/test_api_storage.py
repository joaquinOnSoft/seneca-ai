"""
tests/seneca/core/test_api_storage.py – Unit tests for :class:`ApiConversationStore`.

The :class:`SenecaApiClient` is replaced by a mock, so no API server is needed.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from seneca.api.client import ConversationData, ConversationMessage, SenecaServerError
from seneca.core.api_storage import (
    ApiConversationStore,
    conversation_from_api,
    message_to_api,
)
from seneca.core.conversation import Conversation, Message, Role

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
    client = MagicMock()
    client.create_conversation.return_value = _conv_data()
    return client


@pytest.fixture
def store(api_client):
    return ApiConversationStore(api_client)


def _chat(*texts):
    conv = Conversation()
    for i, text in enumerate(texts):
        conv.add_message(Role.USER if i % 2 == 0 else Role.ASSISTANT, text)
    return conv


class TestConversions:
    def test_roles_are_sent_in_lowercase(self):
        assert message_to_api(Message(Role.USER, "hi")).role == "user"
        assert message_to_api(Message(Role.ASSISTANT, "hi")).role == "assistant"

    def test_naive_timestamp_is_sent_with_offset(self):
        msg = message_to_api(Message(Role.USER, "hi", timestamp=datetime(2026, 1, 1, 10, 0)))
        assert datetime.fromisoformat(msg.timestamp).tzinfo is not None

    def test_conversation_from_api(self):
        data = _conv_data(messages=[
            ConversationMessage("user", "Hola", "2026-01-01T10:00:00Z"),
            ConversationMessage("assistant", "¡Hola!", "2026-01-01T10:00:02+00:00"),
        ])
        conv = conversation_from_api(data)
        assert conv.id == SERVER_ID
        assert conv.title == "Hola"
        assert [m.role for m in conv.messages] == [Role.USER, Role.ASSISTANT]
        # Converted to naive local time, like the datetimes created by the app
        assert conv.created_at.tzinfo is None
        expected = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        assert conv.created_at == expected

    def test_round_trip_keeps_the_instant(self):
        original = Message(Role.USER, "hi", timestamp=datetime(2026, 5, 4, 12, 30))
        sent = message_to_api(original)
        back = conversation_from_api(_conv_data(messages=[sent])).messages[0]
        assert back.timestamp == original.timestamp


class TestSave:
    def test_first_save_creates_conversation_and_takes_server_id(self, store, api_client):
        conv = _chat("Hola, ¿qué tal?", "Bien")

        store.save_conversation(conv)

        api_client.create_conversation.assert_called_once()
        title, messages = api_client.create_conversation.call_args.args
        assert title == "Hola, ¿qué tal?"
        assert [m.role for m in messages] == ["user", "assistant"]
        assert conv.id == SERVER_ID

    def test_next_saves_only_append_new_messages(self, store, api_client):
        conv = _chat("Hola", "Bien")
        store.save_conversation(conv)

        conv.add_message(Role.USER, "Otra")
        conv.add_message(Role.ASSISTANT, "Respuesta")
        store.save_conversation(conv)

        api_client.create_conversation.assert_called_once()
        conv_id, messages = api_client.append_messages.call_args.args
        assert conv_id == SERVER_ID
        assert [m.content for m in messages] == ["Otra", "Respuesta"]

    def test_save_without_changes_does_nothing(self, store, api_client):
        conv = _chat("Hola", "Bien")
        store.save_conversation(conv)
        store.save_conversation(conv)
        api_client.append_messages.assert_not_called()

    def test_failed_append_is_retried_on_next_save(self, store, api_client):
        conv = _chat("Hola", "Bien")
        store.save_conversation(conv)

        conv.add_message(Role.USER, "Otra")
        api_client.append_messages.side_effect = requests.ConnectionError("down")
        store.save_conversation(conv)  # must not raise

        api_client.append_messages.side_effect = None
        conv.add_message(Role.ASSISTANT, "Respuesta")
        store.save_conversation(conv)
        _, messages = api_client.append_messages.call_args.args
        assert [m.content for m in messages] == ["Otra", "Respuesta"]

    def test_api_error_on_create_does_not_raise(self, store, api_client):
        api_client.create_conversation.side_effect = SenecaServerError("boom", status_code=500)
        conv = _chat("Hola")
        store.save_conversation(conv)
        assert conv.id != SERVER_ID


class TestLoad:
    def test_load_returns_summaries(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        result = store.load_conversations(20)
        assert [c.id for c in result] == [SERVER_ID]
        assert result[0].messages == []
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

    def test_continue_loaded_conversation_appends(self, store, api_client):
        api_client.list_conversations.return_value = [_conv_data()]
        api_client.get_conversation.return_value = _conv_data(messages=[
            ConversationMessage("user", "Hola", "2026-01-01T10:00:00Z"),
        ])
        conv = store.load_conversations()[0]
        store.ensure_messages(conv)

        conv.add_message(Role.ASSISTANT, "¡Hola!")
        store.save_conversation(conv)

        api_client.create_conversation.assert_not_called()
        _, messages = api_client.append_messages.call_args.args
        assert [m.content for m in messages] == ["¡Hola!"]

    def test_ensure_messages_ignores_new_local_conversations(self, store, api_client):
        store.ensure_messages(_chat("Hola"))
        api_client.get_conversation.assert_not_called()


class TestDelete:
    def test_delete_stored_conversation(self, store, api_client):
        conv = _chat("Hola")
        store.save_conversation(conv)
        store.delete_conversation(conv)
        api_client.delete_conversation.assert_called_once_with(SERVER_ID)

    def test_delete_unsaved_conversation_is_noop(self, store, api_client):
        store.delete_conversation(_chat("Hola"))
        api_client.delete_conversation.assert_not_called()
