"""
tests/seneca/core/test_agent.py – Unit tests for the desktop :class:`SenecaAgent`.

The API client is replaced by a fake that returns scripted event streams,
so no API server or LLM is needed.
"""

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from seneca.api.client import ChatCapabilities, ChatEvent, SenecaServiceUnavailableError
from seneca.core.agent import SenecaAgent
from seneca.core.conversation import Conversation, Role


class FakeStream:
    """Iterable of ChatEvent objects with the close() of a ChatStream."""

    def __init__(self, events, block_after=None):
        self.events = events
        self.closed = False
        self.block_after = block_after      # index after which the stream waits until closed
        self.unblocked = threading.Event()

    def __iter__(self):
        for i, (name, data) in enumerate(self.events):
            if self.closed:
                return
            yield ChatEvent(name, data)
            if self.block_after == i:
                self.unblocked.wait(timeout=5)
                return

    def close(self):
        self.closed = True
        self.unblocked.set()


def make_client(*streams, tool_calling=True):
    client = MagicMock()
    client.stream_chat.side_effect = list(streams)
    client.get_chat_capabilities.return_value = ChatCapabilities("ollama", "m", tool_calling)
    return client


class Recorder:
    def __init__(self):
        self.tokens, self.done, self.errors = [], [], []
        self.finished = threading.Event()

    def on_token(self, token):
        self.tokens.append(token)

    def on_done(self, reply):
        self.done.append(reply)
        self.finished.set()

    def on_error(self, message):
        self.errors.append(message)
        self.finished.set()


def ask(agent, conv, text="Hola"):
    conv.add_message(Role.USER, text)
    rec = Recorder()
    agent.stream_reply(conv, rec.on_token, rec.on_done, rec.on_error)
    return rec


def wait(rec):
    assert rec.finished.wait(timeout=5), "the agent did not finish"
    return rec


def save_text_to_file(text: str, file_name: str) -> str:
    """Save text to a file."""
    return f"saved {file_name}: {text}"


def test_new_conversation_takes_server_id_and_title():
    client = make_client(FakeStream([
        ("conversation", {"id": "srv-1", "title": "Hola", "created": True}),
        ("token", {"text": "Ho"}), ("token", {"text": "la"}),
        ("done", {"message": {"role": "assistant", "content": "Hola"}}),
    ]))
    agent, conv = SenecaAgent(client), Conversation()

    rec = wait(ask(agent, conv))

    assert rec.tokens == ["Ho", "la"] and rec.done == ["Hola"] and not rec.errors
    assert (conv.id, conv.title, conv.stored) == ("srv-1", "Hola", True)
    kwargs = client.stream_chat.call_args.kwargs
    assert kwargs == {"content": "Hola", "conversation_id": None, "tools": []}


def test_stored_conversation_sends_its_id():
    client = make_client(FakeStream([("conversation", {"id": "srv-1", "title": "t", "created": False}),
                                     ("done", {"message": None})]))
    conv = Conversation(id="srv-1", stored=True)
    wait(ask(SenecaAgent(client), conv, "Otra"))
    assert client.stream_chat.call_args.kwargs["conversation_id"] == "srv-1"
    assert client.stream_chat.call_args.kwargs["content"] == "Otra"


def test_tools_run_locally_and_results_resume_the_reply():
    client = make_client(
        FakeStream([("conversation", {"id": "srv-1", "title": "t", "created": True}),
                    ("token", {"text": "Voy. "}),
                    ("tool_calls", {"tool_calls": [{"id": "c1", "name": "save_text_to_file",
                                                    "args": {"text": "hola", "file_name": "a.txt"}}]})]),
        FakeStream([("conversation", {"id": "srv-1", "title": "t", "created": False}),
                    ("token", {"text": "Hecho."}), ("done", {"message": None})]),
    )
    agent = SenecaAgent(client)
    agent.add_tool(save_text_to_file)

    rec = wait(ask(agent, Conversation()))

    assert rec.done == ["Voy. Hecho."]
    first, second = client.stream_chat.call_args_list
    assert first.kwargs["tools"][0]["name"] == "save_text_to_file"
    assert first.kwargs["tools"][0]["parameters"]["required"] == ["text", "file_name"]
    assert second.kwargs == {
        "conversation_id": "srv-1",
        "tool_results": [{"tool_call_id": "c1", "content": "saved a.txt: hola"}],
        "tools": first.kwargs["tools"],
    }


def test_unknown_or_failing_tool_reports_an_error_result():
    def broken(text: str) -> str:
        """Always fails."""
        raise PermissionError("denied")

    client = make_client(
        FakeStream([("conversation", {"id": "s", "title": "t", "created": True}),
                    ("tool_calls", {"tool_calls": [{"id": "c1", "name": "broken", "args": {"text": "x"}},
                                                   {"id": "c2", "name": "missing", "args": {}}]})]),
        FakeStream([("done", {"message": None})]),
    )
    agent = SenecaAgent(client)
    agent.add_tool(broken)
    wait(ask(agent, Conversation()))

    results = client.stream_chat.call_args_list[1].kwargs["tool_results"]
    assert results[0]["tool_call_id"] == "c1" and "denied" in results[0]["content"]
    assert results[1] == {"tool_call_id": "c2", "content": "Error: tool 'missing' not found."}


def test_error_event_is_reported():
    client = make_client(FakeStream([("conversation", {"id": "s", "title": "t", "created": True}),
                                     ("error", {"error": "model crashed"})]))
    rec = wait(ask(SenecaAgent(client), Conversation()))
    assert rec.errors == ["model crashed"] and not rec.done


def test_http_error_is_reported():
    client = make_client()
    client.stream_chat.side_effect = SenecaServiceUnavailableError("Database service unavailable.", 503)
    rec = wait(ask(SenecaAgent(client), Conversation()))
    assert rec.errors == ["Database service unavailable."]


def test_connection_error_is_reported():
    client = make_client()
    client.stream_chat.side_effect = requests.ConnectionError("refused")
    rec = wait(ask(SenecaAgent(client), Conversation()))
    assert rec.errors == ["Cannot connect to the Seneca AI API server."]


def test_cancel_closes_the_stream_and_keeps_the_partial_reply():
    stream = FakeStream([("conversation", {"id": "s", "title": "t", "created": True}),
                         ("token", {"text": "Parcial"}), ("token", {"text": " nunca"})], block_after=1)
    agent = SenecaAgent(make_client(stream))
    rec = ask(agent, Conversation())

    while not rec.tokens:  # wait for the first token
        threading.Event().wait(0.01)
    agent.cancel()

    wait(rec)
    assert stream.closed
    assert rec.done == ["Parcial"] and not rec.errors


def test_tools_are_not_added_when_the_model_does_not_support_them():
    agent = SenecaAgent(make_client(tool_calling=False))
    agent.add_tool(save_text_to_file)
    assert agent._tool_specs() == []


def test_supports_tools_is_asked_once():
    client = make_client()
    agent = SenecaAgent(client)
    assert agent.supports_tools() and agent.supports_tools()
    client.get_chat_capabilities.assert_called_once()


def test_supports_tools_when_api_is_down_waits_before_retrying():
    client = make_client()
    client.get_chat_capabilities.side_effect = requests.ConnectionError("down")
    agent = SenecaAgent(client)
    assert agent.supports_tools() is False
    assert agent.supports_tools() is False
    client.get_chat_capabilities.assert_called_once()


def test_remove_tool_and_reset():
    agent = SenecaAgent(make_client())
    agent.add_tool(save_text_to_file)
    agent.remove_tool(save_text_to_file)
    assert agent._tool_specs() == []
    agent.add_tool(save_text_to_file)
    agent.reset()
    assert agent._tool_specs() == []


def test_cancel_while_a_tool_runs_does_not_send_its_results():
    first = FakeStream([("conversation", {"id": "s", "title": "t", "created": True}),
                        ("tool_calls", {"tool_calls": [{"id": "c1", "name": "slow", "args": {}}]})])
    client = make_client(first)
    agent = SenecaAgent(client)

    def slow() -> str:
        """Takes a while; the user cancels meanwhile."""
        agent.cancel()
        return "done"

    agent.add_tool(slow)
    rec = wait(ask(agent, Conversation()))
    assert client.stream_chat.call_count == 1
    assert rec.done == [""]
