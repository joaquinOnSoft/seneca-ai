"""
src/seneca/memory/turns.py – Split a stored conversation into turns.

A turn is a user message plus the assistant messages that follow it. Turns
are the unit indexed in Qdrant: a question together with its answer gives
much better search results than single messages.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

# Namespace of the deterministic point ids (uuid5). Never change it: the ids
# of the points already stored in Qdrant depend on it.
POINT_NAMESPACE = uuid.UUID("6f1c2b0e-5d0a-4e6b-9a51-3c2f0e8d7a41")

# Characters of a turn that are embedded and stored (longer turns are cut)
MAX_TURN_CHARS = 4_000

USER_LABEL = "Usuario"
ASSISTANT_LABEL = "Seneca"


@dataclass
class Turn:
    """A user message and the assistant replies that follow it."""

    index: int
    user: str = ""
    assistant: List[str] = field(default_factory=list)
    timestamp: str = ""

    @property
    def complete(self) -> bool:
        """Whether the assistant has replied (only complete turns are indexed)."""
        return any(text.strip() for text in self.assistant)

    def text(self, max_chars: int = MAX_TURN_CHARS) -> str:
        """Text that is embedded and shown in the prompt."""
        parts = []
        if self.user.strip():
            parts.append(f"{USER_LABEL}: {self.user.strip()}")
        reply = "\n".join(text.strip() for text in self.assistant if text.strip())
        if reply:
            parts.append(f"{ASSISTANT_LABEL}: {reply}")
        text = "\n".join(parts)
        return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def split_turns(messages: List[Dict[str, Any]]) -> List[Turn]:
    """Group stored ``{"role", "content", "timestamp"}`` messages into turns.

    Assistant messages before the first user message (if any) form a turn
    without a user part. Messages with other roles are ignored.
    """
    turns: List[Turn] = []
    for message in messages:
        role, content = message.get("role"), message.get("content") or ""
        if role == "user":
            turns.append(Turn(index=len(turns), user=content, timestamp=message.get("timestamp", "")))
        elif role == "assistant":
            if not turns:
                turns.append(Turn(index=0, timestamp=message.get("timestamp", "")))
            turns[-1].assistant.append(content)
    return turns


def complete_turns(messages: List[Dict[str, Any]]) -> List[Turn]:
    """The turns that can be indexed: every turn up to the last one with a reply.

    A trailing turn without a reply is still being answered, so it waits.
    A turn without a reply that is followed by other turns (the reply
    failed) is kept, so the turn numbering never changes.
    """
    turns = split_turns(messages)
    while turns and not turns[-1].complete:
        turns.pop()
    return turns


def turn_point_id(conversation_id: str, turn_index: int) -> str:
    """Deterministic Qdrant point id: re-indexing a turn overwrites its point."""
    return str(uuid.uuid5(POINT_NAMESPACE, f"{conversation_id}:{turn_index}"))


def summary_point_id(conversation_id: str) -> str:
    """Deterministic Qdrant point id of a conversation's running summary."""
    return str(uuid.uuid5(POINT_NAMESPACE, f"{conversation_id}:summary"))
