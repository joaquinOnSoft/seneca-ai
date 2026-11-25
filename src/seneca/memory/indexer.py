"""
src/seneca/memory/indexer.py – Index MongoDB conversations into Qdrant.

MongoDB works as the job queue (outbox pattern): a conversation needs work
when its ``updated_at`` is newer than ``memory.synced_at``, or when it was
indexed into another collection (a different embedding model). Nothing is
lost if the worker stops: it picks up the pending conversations when it
starts again.

State kept in each conversation document (``memory``):

``collection``     Qdrant collection the conversation is indexed in
``indexed_turns``  complete turns already stored
``title``          title stored in the points' payload
``summary``        running summary of the conversation
``summary_turns``  turns covered by the summary
``synced_at``      ``updated_at`` of the conversation when it was indexed
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from seneca.memory.embedder import Embedder
from seneca.memory.store import MemoryPoint, TurnStore
from seneca.memory.turns import Turn, complete_turns, summary_point_id, turn_point_id

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Actualiza el resumen de una conversación entre un usuario y Seneca-AI con "
    "los mensajes nuevos. Conserva lo importante: temas, decisiones, datos y "
    "preferencias del usuario. Escribe como máximo {max_words} palabras, en el "
    "idioma de la conversación, sin introducciones ni comentarios."
)


class MemoryDb(Protocol):
    """MongoDB operations used by the indexer (see seneca.api.database)."""

    def conversations_to_index(self, collection: str, limit: int) -> List[Dict[str, Any]]: ...

    def set_memory_state(self, conv_id: str, memory: Dict[str, Any]) -> None: ...

    def existing_conversation_ids(self, conv_ids: List[str]) -> set: ...


class LlmSummarizer:
    """Keeps a running summary of a conversation with the chat LLM."""

    def __init__(self, llm_factory: Callable[[], Any], max_words: int = 200) -> None:
        self._llm_factory = llm_factory
        self._max_words = max_words

    def summarize(self, previous: str, turns: List[Turn]) -> str:
        new_messages = "\n\n".join(turn.text() for turn in turns)
        prompt = f"Resumen actual:\n{previous.strip() or '(vacío)'}\n\nMensajes nuevos:\n{new_messages}"
        reply = self._llm_factory().invoke([
            SystemMessage(content=SUMMARY_PROMPT.format(max_words=self._max_words)),
            HumanMessage(content=prompt),
        ])
        return (reply.text or "").strip()


class MemoryIndexer:
    """Embeds new conversation turns and stores them in Qdrant.

    Parameters
    ----------
    summarizer:
        Optional :class:`LlmSummarizer`; ``None`` disables the summaries.
    summary_every:
        The summary is updated every this many new turns (0 disables it).
    batch_size:
        Turns embedded per request to Ollama.
    """

    def __init__(self, db: MemoryDb, embedder: Embedder, store: TurnStore,
                 summarizer: Optional[LlmSummarizer] = None, summary_every: int = 6,
                 batch_size: int = 16) -> None:
        self.db = db
        self.embedder = embedder
        self.store = store
        self.summarizer = summarizer
        self.summary_every = summary_every
        self.batch_size = batch_size
        # Vector size of the embedding model; set by the worker on start, so
        # the collection can be recreated if it is dropped (--reindex)
        self.dimensions: Optional[int] = None

    def run_once(self, limit: int = 20) -> int:
        """Index the conversations waiting for it. Returns how many were processed."""
        conversations = self.db.conversations_to_index(self.store.collection, limit)
        if conversations and self.dimensions and not self.store.exists():
            self.store.ensure_collection(self.dimensions)
        done = 0
        for conversation in conversations:
            try:
                self.index_conversation(conversation)
                done += 1
            except Exception as exc:  # noqa: BLE001 – retried on the next pass
                logger.error("Could not index conversation %s: %s", conversation.get("_id"), exc)
        return done

    def index_conversation(self, conversation: Dict[str, Any]) -> None:
        conv_id = str(conversation["_id"])
        user_id = conversation.get("user_id", "")
        title = conversation.get("title", "")
        memory = dict(conversation.get("memory") or {})
        turns = complete_turns(conversation.get("messages", []))

        # New conversation, new embedding model, or messages replaced/removed:
        # start again from the first turn
        if memory.get("collection") != self.store.collection or memory.get("indexed_turns", 0) > len(turns):
            self.store.delete_conversation(conv_id)
            memory = {"collection": self.store.collection, "indexed_turns": 0,
                      "summary": "", "summary_turns": 0, "title": title}
        elif memory.get("title") != title:
            self.store.set_title(conv_id, title)
            memory["title"] = title

        base = {"user_id": user_id, "conversation_id": conv_id, "conversation_title": title}
        new_turns = [turn for turn in turns[memory.get("indexed_turns", 0):] if turn.text()]
        for start in range(0, len(new_turns), self.batch_size):
            batch = new_turns[start:start + self.batch_size]
            vectors = self.embedder.embed([turn.text() for turn in batch])
            self.store.upsert(
                MemoryPoint(turn_point_id(conv_id, turn.index), vector,
                            {**base, "kind": "turn", "turn_index": turn.index,
                             "created_at": turn.timestamp, "text": turn.text()})
                for turn, vector in zip(batch, vectors))
        memory["indexed_turns"] = len(turns)

        self._update_summary(conv_id, base, turns, memory)

        memory["synced_at"] = conversation.get("updated_at")
        self.db.set_memory_state(conv_id, memory)
        if new_turns:
            logger.info("Indexed %d turns of conversation %s.", len(new_turns), conv_id)

    def _update_summary(self, conv_id: str, base: Dict[str, Any], turns: List[Turn],
                        memory: Dict[str, Any]) -> None:
        if not self.summarizer or self.summary_every <= 0:
            return
        if len(turns) - memory.get("summary_turns", 0) < self.summary_every:
            return
        summary = memory.get("summary", "")
        try:
            # In steps, so a long conversation indexed for the first time does
            # not overflow the context of a small model
            for start in range(memory.get("summary_turns", 0), len(turns), self.summary_every):
                summary = self.summarizer.summarize(summary, turns[start:start + self.summary_every])
            vector = self.embedder.embed([summary])[0]
        except Exception as exc:  # noqa: BLE001 – the turns are indexed anyway
            logger.warning("Could not update the summary of conversation %s: %s", conv_id, exc)
            return
        if not summary:
            return
        self.store.upsert([MemoryPoint(summary_point_id(conv_id), vector,
                                       {**base, "kind": "summary", "turn_index": -1,
                                        "created_at": turns[-1].timestamp, "text": summary})])
        memory["summary"] = summary
        memory["summary_turns"] = len(turns)

    def cleanup(self) -> int:
        """Delete the points of conversations that no longer exist in MongoDB."""
        if not self.store.exists():
            return 0
        indexed = sorted(self.store.conversation_ids())
        removed = 0
        for start in range(0, len(indexed), 500):
            chunk = indexed[start:start + 500]
            existing = self.db.existing_conversation_ids(chunk)
            for conv_id in set(chunk) - existing:
                self.store.delete_conversation(conv_id)
                removed += 1
        if removed:
            logger.info("Removed the memory of %d deleted conversations.", removed)
        return removed
