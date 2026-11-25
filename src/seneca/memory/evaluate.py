"""
src/seneca/memory/evaluate.py – Measure how well memory finds past conversations.

Write 20-30 questions about your own past conversations, each with the id of
the conversation that answers it, and run::

    docker compose exec -T memory-worker python -m seneca.memory.evaluate --user <user_id> - < cases.json

``cases.json``::

    [
      {"question": "¿Qué hotel me recomendaste en Lisboa?",
       "conversation_id": "6553f1a2b3c4d5e6f7a8b9c0"},
      ...
    ]

For each question it reports the rank of the expected conversation among the
results, then recall@k (share of questions whose conversation is in the top
k) and MRR. The search ignores ``MEMORY_MIN_SCORE`` and prints the scores, so
you can choose the threshold: a good one keeps the expected hits and drops
the rest. Use the numbers to compare settings (threshold, embedding model)
and to decide whether fact memory (phase 2, Mem0) is needed.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from seneca.memory.embedder import OllamaEmbedder
from seneca.memory.service import MemoryService
from seneca.memory.store import TurnStore, collection_name


def evaluate(service: MemoryService, user_id: str, cases: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
    """Rank of the expected conversation for each case, plus recall@k and MRR."""
    results = []
    for case in cases:
        hits = service.search(user_id, case["question"], limit=top_k, min_score=0.0)
        conversations = [hit.conversation_id for hit in hits]
        rank = conversations.index(case["conversation_id"]) + 1 if case["conversation_id"] in conversations else None
        expected_score = hits[rank - 1].score if rank else None
        results.append({"question": case["question"], "rank": rank, "expected_score": expected_score,
                        "top_score": hits[0].score if hits else None})
    total = len(results) or 1
    recall = {k: sum(1 for r in results if r["rank"] and r["rank"] <= k) / total for k in (1, 3, top_k)}
    mrr = sum(1 / r["rank"] for r in results if r["rank"]) / total
    return {"cases": results, "recall": recall, "mrr": mrr}


def main(argv: Optional[List[str]] = None) -> int:
    from seneca.utils.config import config  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Evaluate the memory search (recall@k)")
    parser.add_argument("cases", help="JSON file with the cases, or - for stdin")
    parser.add_argument("--user", required=True, help="user_id that owns the conversations")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)

    with (sys.stdin if args.cases == "-" else open(args.cases, encoding="utf-8")) as f:
        cases = json.load(f)

    embedder = OllamaEmbedder(config.ollama_base_url, config.embedding_model, timeout=120)
    store = TurnStore.connect(config.qdrant_url, collection_name(config.embedding_model),
                              api_key=config.qdrant_api_key)
    report = evaluate(MemoryService(embedder, store), args.user, cases, args.top_k)

    for case in report["cases"]:
        rank = case["rank"] or "-"
        score = f"{case['expected_score']:.3f}" if case["expected_score"] is not None else "  -  "
        top = f"{case['top_score']:.3f}" if case["top_score"] is not None else "  -  "
        print(f"rank {rank!s:>2}  score {score}  top {top}  {case['question']}")
    print()
    for k, value in report["recall"].items():
        print(f"recall@{k}: {value:.2f}")
    print(f"MRR: {report['mrr']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
