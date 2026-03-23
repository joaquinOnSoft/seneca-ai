"""
tests/unit/test_conversation.py – Unit tests for the Conversation model.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import pytest
from seneca.core.conversation import Conversation, Message, Role


class TestMessage:
    def test_defaults(self):
        msg = Message(role=Role.USER, content="Hello")
        assert msg.role == Role.USER
        assert msg.content == "Hello"
        assert msg.id  # UUID generated

    def test_role_enum(self):
        assert Role.USER != Role.ASSISTANT


class TestConversation:
    def test_add_message(self):
        conv = Conversation()
        msg = conv.add_message(Role.USER, "Hi Seneca")
        assert len(conv.messages) == 1
        assert msg.content == "Hi Seneca"

    def test_derive_title_from_first_user_message(self):
        conv = Conversation()
        conv.add_message(Role.USER, "What is the capital of France?")
        conv.add_message(Role.ASSISTANT, "Paris.")
        assert conv.derive_title() == "What is the capital of France?"

    def test_derive_title_truncates_long_message(self):
        conv = Conversation()
        long_text = "A" * 50
        conv.add_message(Role.USER, long_text)
        title = conv.derive_title()
        assert len(title) <= 40
        assert title.endswith("…")

    def test_derive_title_no_user_message(self):
        conv = Conversation(title="Fallback")
        title = conv.derive_title()
        assert title == "Fallback"

    def test_to_langchain_messages(self):
        conv = Conversation()
        conv.add_message(Role.USER, "Hello")
        conv.add_message(Role.ASSISTANT, "Hi!")
        lc = conv.to_langchain_messages()
        assert lc[0] == {"role": "human", "content": "Hello"}
        assert lc[1] == {"role": "ai", "content": "Hi!"}

    def test_unique_ids(self):
        c1 = Conversation()
        c2 = Conversation()
        assert c1.id != c2.id
