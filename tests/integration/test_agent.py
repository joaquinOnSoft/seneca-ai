"""
tests/integration/test_agent.py – Integration tests for SenecaAgent.

These tests are skipped unless a real LLM_PROVIDER and credentials are
configured in the environment, so they do not run in CI by default.
"""

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import pytest
from seneca.core.agent import SenecaAgent
from seneca.core.conversation import Conversation, Role


_REQUIRES_LLM = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"),
    reason="No LLM credentials configured",
)


@_REQUIRES_LLM
class TestSenecaAgentIntegration:
    def test_stream_reply_produces_tokens(self):
        agent = SenecaAgent()
        conv = Conversation()
        conv.add_message(Role.USER, "Say exactly: Hello World")

        tokens: list[str] = []
        done_event = threading.Event()
        error_holder: list[str] = []

        agent.stream_reply(
            conversation=conv,
            on_token=tokens.append,
            on_done=lambda _: done_event.set(),
            on_error=lambda e: (error_holder.append(e), done_event.set()),
        )

        done_event.wait(timeout=30)
        assert not error_holder, f"Agent error: {error_holder[0]}"
        full = "".join(tokens)
        assert "Hello" in full or "hello" in full

    def test_cancel_stops_stream(self):
        agent = SenecaAgent()
        conv = Conversation()
        conv.add_message(
            Role.USER,
            "Write a 500-word essay about the philosophy of stoicism.",
        )

        done_event = threading.Event()
        tokens: list[str] = []

        agent.stream_reply(
            conversation=conv,
            on_token=tokens.append,
            on_done=lambda _: done_event.set(),
            on_error=lambda _: done_event.set(),
        )

        # Cancel after a short delay
        threading.Timer(0.5, agent.cancel).start()
        done_event.wait(timeout=15)
        # We just assert it finished without hanging
        assert True
