"""
tests/unit/test_storage.py – Unit tests for the JSON conversation store.

Uses a temporary directory to avoid touching ~/.seneca.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import pytest
from seneca.core.conversation import Conversation, Role
import seneca.core.storage as storage_module


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    """Redirect the store to a temporary directory."""
    store_dir = tmp_path / ".seneca"
    store_file = store_dir / "conversations.json"
    monkeypatch.setattr(storage_module, "_STORE_DIR", store_dir)
    monkeypatch.setattr(storage_module, "_STORE_FILE", store_file)
    yield store_file


def _make_conv(user_text: str) -> Conversation:
    conv = Conversation()
    conv.add_message(Role.USER, user_text)
    conv.add_message(Role.ASSISTANT, "Response.")
    return conv


class TestStorage:
    def test_load_empty_store(self):
        result = storage_module.load_conversations()
        assert result == []

    def test_save_and_load(self):
        conv = _make_conv("Hello")
        storage_module.save_conversation(conv)
        loaded = storage_module.load_conversations()
        assert len(loaded) == 1
        assert loaded[0].id == conv.id

    def test_save_updates_existing(self):
        conv = _make_conv("First")
        storage_module.save_conversation(conv)
        conv.add_message(Role.USER, "Second")
        storage_module.save_conversation(conv)
        loaded = storage_module.load_conversations()
        assert len(loaded) == 1
        assert len(loaded[0].messages) == 3

    def test_respects_limit(self):
        for i in range(25):
            storage_module.save_conversation(_make_conv(f"Message {i}"))
        loaded = storage_module.load_conversations(limit=10)
        assert len(loaded) <= 10

    def test_delete_all(self):
        storage_module.save_conversation(_make_conv("Keep me not"))
        storage_module.delete_all()
        assert storage_module.load_conversations() == []

    def test_messages_round_trip(self):
        conv = _make_conv("Round trip test")
        storage_module.save_conversation(conv)
        loaded = storage_module.load_conversations()[0]
        assert loaded.messages[0].content == "Round trip test"
        assert loaded.messages[0].role == Role.USER
        assert loaded.messages[1].role == Role.ASSISTANT
