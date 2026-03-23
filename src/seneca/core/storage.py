"""
src/seneca/core/storage.py – Lightweight JSON-based conversation store.

Conversations are persisted to ``~/.seneca/conversations.json`` so
that the sidebar list survives across sessions.  The format is
intentionally simple – no external DB dependency.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from seneca.core.conversation import Conversation, Message, Role

logger = logging.getLogger(__name__)

_STORE_DIR = Path.home() / ".seneca"
_STORE_FILE = _STORE_DIR / "conversations.json"


def _ensure_store() -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    if not _STORE_FILE.exists():
        _STORE_FILE.write_text("[]", encoding="utf-8")


def _serialise(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role.name,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in conv.messages
        ],
    }


def _deserialise(data: dict) -> Conversation:
    from datetime import datetime

    conv = Conversation(
        id=data["id"],
        title=data["title"],
    )
    conv.created_at = datetime.fromisoformat(data["created_at"])
    conv.messages = [
        Message(
            id=m["id"],
            role=Role[m["role"]],
            content=m["content"],
            timestamp=datetime.fromisoformat(m["timestamp"]),
        )
        for m in data.get("messages", [])
    ]
    return conv


def load_conversations(limit: int = 20) -> list[Conversation]:
    """Load the *limit* most recent conversations from disk."""
    _ensure_store()
    try:
        raw = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        conversations = [_deserialise(d) for d in raw]
        return sorted(
            conversations,
            key=lambda c: c.created_at,
            reverse=True,
        )[:limit]
    except Exception as exc:
        logger.warning("Could not load conversations: %s", exc)
        return []


def save_conversation(conv: Conversation) -> None:
    """Persist *conv*, replacing any existing entry with the same id."""
    _ensure_store()
    try:
        raw = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
        existing = {d["id"]: d for d in raw}
        existing[conv.id] = _serialise(conv)
        _STORE_FILE.write_text(
            json.dumps(list(existing.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.error("Could not save conversation: %s", exc)


def delete_all() -> None:
    """Wipe all stored conversations."""
    _ensure_store()
    _STORE_FILE.write_text("[]", encoding="utf-8")
