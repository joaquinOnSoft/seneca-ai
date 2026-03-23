"""
src/seneca/core/conversation.py – Domain models for chat history.

These plain dataclasses carry no UI or I/O logic; they are the
single source of truth for what was said and by whom.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class Role(Enum):
    """Speaker role in a conversation turn."""
    USER = auto()
    ASSISTANT = auto()


@dataclass
class Message:
    """A single turn in a conversation."""
    role: Role
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Conversation:
    """An ordered sequence of messages with a unique identifier."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Nueva conversación"
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: Role, content: str) -> Message:
        """Append a new :class:`Message` and return it."""
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        return msg

    def derive_title(self) -> str:
        """
        Derive a short title from the first user message.
        Truncates at 40 characters.
        """
        for msg in self.messages:
            if msg.role == Role.USER:
                raw = msg.content.strip().replace("\n", " ")
                return raw[:37] + "…" if len(raw) > 40 else raw
        return self.title

    def to_langchain_messages(self) -> list[dict[str, str]]:
        """
        Convert to the ``[{"role": ..., "content": ...}]`` format
        expected by LangChain chat models.
        """
        role_map = {Role.USER: "human", Role.ASSISTANT: "ai"}
        return [
            {"role": role_map[m.role], "content": m.content}
            for m in self.messages
        ]
