"""
src/seneca/memory/embedder.py – Text embeddings.

:class:`Embedder` is the interface used by the rest of the memory package;
:class:`OllamaEmbedder` implements it with an embedding model served by the
``ollama`` container (``bge-m3`` by default: multilingual, 1024 dimensions).
Another provider (e.g. a hosted API) only needs a new class.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Turns texts into vectors."""

    model: str

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """One vector per text, in the same order."""
        ...


class OllamaEmbedder:
    """Embeddings from Ollama's ``/api/embed``.

    Parameters
    ----------
    base_url:
        Ollama server, e.g. ``http://ollama:11434``.
    model:
        Embedding model name, e.g. ``bge-m3``.
    timeout:
        Seconds per request. Keep it short where the caller waits (the chat
        searches memory before answering) and long in the worker.
    keep_alive:
        How long Ollama keeps the model loaded after a request.
    """

    def __init__(self, base_url: str, model: str, timeout: Optional[float] = None,
                 keep_alive: Optional[str] = None) -> None:
        import ollama  # noqa: PLC0415 – only needed when memory is enabled

        self.model = model
        self._keep_alive = keep_alive
        self._client = ollama.Client(host=base_url, timeout=timeout)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        response = self._client.embed(model=self.model, input=list(texts), keep_alive=self._keep_alive)
        return [list(vector) for vector in response.embeddings]

    def ensure_model(self) -> None:
        """Download the model into Ollama if it is not there yet (can take minutes)."""
        import ollama  # noqa: PLC0415

        try:
            self._client.show(self.model)
            return
        except ollama.ResponseError as exc:
            if exc.status_code != 404:
                raise
        logger.info("Pulling the embedding model '%s' into Ollama…", self.model)
        self._client.pull(self.model)
        logger.info("Embedding model '%s' ready.", self.model)
