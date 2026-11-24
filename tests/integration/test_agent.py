"""
tests/integration/test_agent.py – End-to-end chat through a running Seneca-AI API.

Needs the api container (or ``python src/seneca/api/api.py``) running at
``SENECA_API_BASE_URL`` with a working LLM, and ``SENECA_AI_API_KEY`` in
``.env``.  Skipped when the API (with the /chat endpoint) is not reachable.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
import requests

from seneca.api.client import SenecaApiError
from seneca.core.agent import SenecaAgent
from seneca.core.api_storage import create_api_client
from seneca.core.conversation import Conversation, Role


def _chat_api_available() -> bool:
    try:
        create_api_client(timeout=3.0, max_retries=0).get_chat_capabilities()
        return True
    except (SenecaApiError, requests.RequestException):
        return False


pytestmark = pytest.mark.skipif(not _chat_api_available(),
                                reason="Seneca-AI API with the /chat endpoint is not reachable")


def _ask(agent, conv, text):
    conv.add_message(Role.USER, text)
    tokens, result, done = [], {}, threading.Event()

    def on_done(reply):
        result["reply"] = reply
        done.set()

    def on_error(message):
        result["error"] = message
        done.set()

    agent.stream_reply(conversation=conv, on_token=tokens.append, on_done=on_done, on_error=on_error)
    return tokens, result, done


@pytest.fixture
def conversation():
    """A new conversation, deleted from the server after the test."""
    conv = Conversation()
    yield conv
    if conv.stored:
        create_api_client().delete_conversation(conv.id)


class TestSenecaAgentIntegration:
    def test_stream_reply_produces_tokens_and_stores_the_conversation(self, conversation):
        agent = SenecaAgent()
        tokens, result, done = _ask(agent, conversation, "CRITICAL: Say exactly 'Hello World'")

        assert done.wait(timeout=300), "no reply within 5 minutes"
        assert "error" not in result, f"Agent error: {result.get('error')}"
        assert tokens and "".join(tokens) == result["reply"]
        assert conversation.stored

        stored = create_api_client().get_conversation(conversation.id)
        assert [m.role for m in stored.messages] == ["user", "assistant"]
        assert stored.messages[-1].content == result["reply"]

    def test_cancel_stops_stream(self, conversation):
        agent = SenecaAgent()
        _, result, done = _ask(agent, conversation,
                               "Write a 500-word essay about the philosophy of stoicism.")

        threading.Timer(0.5, agent.cancel).start()
        assert done.wait(timeout=300), "the reply did not stop"
        assert "error" not in result
