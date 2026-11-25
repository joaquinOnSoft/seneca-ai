"""
src/seneca/memory/store.py – Qdrant collection of conversation turns.

One collection per embedding model (``seneca_turns_<model>_v1``): vectors of
different models cannot be compared, so changing ``EMBEDDING_MODEL`` starts
a new collection, and the worker re-indexes every conversation into it.

Each point is a turn (or a conversation summary) with this payload:

``user_id``             owner; every search is filtered by it (tenant index)
``conversation_id``     MongoDB id of the conversation
``conversation_title``  title when the turn was indexed (refreshed on rename)
``kind``                ``"turn"`` or ``"summary"``
``turn_index``          position of the turn in the conversation (-1 for summaries)
``created_at``          timestamp of the turn's user message
``text``                the text that was embedded
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

COLLECTION_PREFIX = "seneca_turns"
# Bump when the payload or the way turns are built changes incompatibly
SCHEMA_VERSION = 1


def collection_name(embedding_model: str) -> str:
    """Name of the collection for *embedding_model*, e.g. ``seneca_turns_bge-m3_v1``."""
    slug = re.sub(r"[^a-z0-9]+", "-", embedding_model.lower()).strip("-") or "default"
    return f"{COLLECTION_PREFIX}_{slug}_v{SCHEMA_VERSION}"


@dataclass
class MemoryPoint:
    """A point to store: its id, vector and payload."""

    id: str
    vector: List[float]
    payload: Dict[str, Any]


@dataclass
class MemoryHit:
    """A search result."""

    score: float
    conversation_id: str
    conversation_title: str
    kind: str
    turn_index: int
    created_at: str
    text: str


class TurnStore:
    """Thin wrapper over a Qdrant collection of turns."""

    def __init__(self, client: QdrantClient, collection: str) -> None:
        self.client = client
        self.collection = collection

    @classmethod
    def connect(cls, url: str, collection: str, api_key: str = "", timeout: int = 10) -> "TurnStore":
        # check_compatibility=False: do not call the server on construction, so
        # the API starts even when Qdrant is still down
        client = QdrantClient(url=url, api_key=api_key or None, timeout=timeout, check_compatibility=False)
        return cls(client, collection)

    # -- collection ------------------------------------------------------------

    def exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def ensure_collection(self, dimensions: int) -> None:
        """Create the collection and its payload indexes if missing."""
        if self.exists():
            size = self._vector_size()
            if size is not None and size != dimensions:
                raise RuntimeError(
                    f"Qdrant collection '{self.collection}' has {size}-dimension vectors but the "
                    f"embedding model returns {dimensions}. Run the worker with --reindex.")
            return
        logger.info("Creating Qdrant collection '%s' (%d dimensions).", self.collection, dimensions)
        self.client.create_collection(
            self.collection,
            vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
        )
        # user_id is the tenant: Qdrant keeps each user's points together,
        # which makes the always-present user filter cheap
        self.client.create_payload_index(
            self.collection, "user_id",
            field_schema=models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD, is_tenant=True))
        self.client.create_payload_index(self.collection, "conversation_id",
                                         field_schema=models.PayloadSchemaType.KEYWORD)

    def _vector_size(self) -> Optional[int]:
        vectors = self.client.get_collection(self.collection).config.params.vectors
        return getattr(vectors, "size", None)

    def drop(self) -> None:
        if self.exists():
            self.client.delete_collection(self.collection)

    # -- points ----------------------------------------------------------------

    def upsert(self, points: Iterable[MemoryPoint]) -> None:
        batch = [models.PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in points]
        if batch:
            self.client.upsert(self.collection, points=batch, wait=True)

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete every point of a conversation."""
        self.client.delete(self.collection, points_selector=models.FilterSelector(
            filter=_match("conversation_id", conversation_id)), wait=True)

    def set_title(self, conversation_id: str, title: str) -> None:
        self.client.set_payload(self.collection, payload={"conversation_title": title},
                                points=_match("conversation_id", conversation_id), wait=True)

    def conversation_ids(self, page_size: int = 512) -> Set[str]:
        """Ids of every conversation with points (used to clean up deleted ones)."""
        ids: Set[str] = set()
        offset = None
        while True:
            points, offset = self.client.scroll(self.collection, limit=page_size, offset=offset,
                                                with_payload=["conversation_id"], with_vectors=False)
            ids.update(p.payload["conversation_id"] for p in points if p.payload)
            if offset is None:
                return ids

    def search(self, vector: List[float], user_id: str, limit: int, min_score: float = 0.0,
               exclude_conversation_id: Optional[str] = None) -> List[MemoryHit]:
        """Nearest points of *user_id* only, best first."""
        must_not = [_condition("conversation_id", exclude_conversation_id)] if exclude_conversation_id else None
        query_filter = models.Filter(must=[_condition("user_id", user_id)], must_not=must_not)
        response = self.client.query_points(self.collection, query=vector, query_filter=query_filter,
                                            limit=limit, score_threshold=min_score or None, with_payload=True)
        return [_hit(point) for point in response.points]


def _condition(key: str, value: str) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def _match(key: str, value: str) -> models.Filter:
    return models.Filter(must=[_condition(key, value)])


def _hit(point) -> MemoryHit:
    payload = point.payload or {}
    return MemoryHit(
        score=point.score,
        conversation_id=payload.get("conversation_id", ""),
        conversation_title=payload.get("conversation_title", ""),
        kind=payload.get("kind", "turn"),
        turn_index=payload.get("turn_index", -1),
        created_at=payload.get("created_at", ""),
        text=payload.get("text", ""),
    )
