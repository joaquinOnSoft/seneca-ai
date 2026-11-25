"""
src/seneca/memory/worker.py – Background process that keeps the memory index up to date.

Runs in the ``memory-worker`` container (same image as ``api``)::

    python -m seneca.memory.worker            # run forever
    python -m seneca.memory.worker --once     # index what is pending and exit
    python -m seneca.memory.worker --reindex  # drop the collection; the running worker rebuilds it
    python -m seneca.memory.worker --reindex --once  # drop it and rebuild it here, then exit

Every ``MEMORY_WORKER_INTERVAL`` seconds it indexes the conversations that
changed (see :mod:`seneca.memory.indexer`), and every
``MEMORY_CLEANUP_INTERVAL`` seconds it removes the points of deleted
conversations.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from typing import List, Optional

from seneca.api.chat import build_llm
from seneca.api.database import MongoDatabase
from seneca.memory.embedder import OllamaEmbedder
from seneca.memory.indexer import LlmSummarizer, MemoryIndexer
from seneca.memory.store import TurnStore, collection_name
from seneca.utils.config import config

logger = logging.getLogger("seneca.memory.worker")

# Seconds between attempts while Ollama, Qdrant or MongoDB are not ready
_STARTUP_RETRY_SECONDS = 10


def build_indexer(cfg) -> tuple[MemoryIndexer, OllamaEmbedder, MongoDatabase]:
    db = MongoDatabase(cfg.mongodb_uri, username=cfg.mongodb_username or None,
                       password=cfg.mongodb_password or None)
    # Indexing is not interactive: allow a slow CPU embedding of a big batch
    embedder = OllamaEmbedder(cfg.ollama_base_url, cfg.embedding_model, timeout=300,
                              keep_alive=cfg.embedding_keep_alive)
    store = TurnStore.connect(cfg.qdrant_url, collection_name(cfg.embedding_model),
                              api_key=cfg.qdrant_api_key, timeout=60)
    summarizer = LlmSummarizer(lambda: build_llm(cfg)) if cfg.memory_summary_every_turns > 0 else None
    indexer = MemoryIndexer(db, embedder, store, summarizer=summarizer,
                            summary_every=cfg.memory_summary_every_turns)
    return indexer, embedder, db


def prepare(indexer: MemoryIndexer, embedder: OllamaEmbedder, db: MongoDatabase, stop: threading.Event) -> bool:
    """Connect to MongoDB, pull the embedding model and create the collection, retrying."""
    while not stop.is_set():
        try:
            db.connect()
            embedder.ensure_model()
            dimensions = len(embedder.embed(["dimension probe"])[0])
            indexer.dimensions = dimensions
            indexer.store.ensure_collection(dimensions)
            logger.info("Memory worker ready: model '%s', collection '%s'.",
                        embedder.model, indexer.store.collection)
            return True
        except Exception as exc:  # noqa: BLE001 – services may still be starting
            logger.warning("Memory worker not ready (%s); retrying in %ds.", exc, _STARTUP_RETRY_SECONDS)
            db.close()
            stop.wait(_STARTUP_RETRY_SECONDS)
    return False


def run(indexer: MemoryIndexer, stop: threading.Event, interval: float, cleanup_interval: float,
        once: bool = False) -> None:
    last_cleanup = 0.0
    while not stop.is_set():
        try:
            processed = indexer.run_once()
            if time.monotonic() - last_cleanup >= cleanup_interval:
                indexer.cleanup()
                last_cleanup = time.monotonic()
        except Exception as exc:  # noqa: BLE001 – keep the worker alive
            logger.error("Memory worker pass failed: %s", exc)
            processed = 0
        if once and processed == 0:
            return
        if processed == 0:
            stop.wait(interval)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seneca AI memory worker")
    parser.add_argument("--once", action="store_true", help="index what is pending and exit")
    parser.add_argument("--reindex", action="store_true",
                        help="drop the Qdrant collection and re-index every conversation")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # MongoDatabase has its own stdout handler: do not print its lines twice
    logging.getLogger("MongoDatabase").propagate = False
    # One line per request to Ollama/Qdrant is noise
    logging.getLogger("httpx").setLevel(logging.WARNING)

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    if not config.memory_enabled:
        logger.info("MEMORY_ENABLED is false; the memory worker is idle.")
        stop.wait()
        return 0

    indexer, embedder, db = build_indexer(config)
    if args.reindex:
        if not prepare(indexer, embedder, db, stop):
            return 1
        logger.info("Re-indexing: dropping collection '%s'.", indexer.store.collection)
        indexer.store.drop()
        db.reset_memory_state()
        # A worker that is already running recreates the collection on its
        # next pass and re-indexes everything; add --once to do it here instead
        if not args.once:
            return 0
    if not prepare(indexer, embedder, db, stop):
        return 0
    run(indexer, stop, config.memory_worker_interval, config.memory_cleanup_interval, once=args.once)
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
