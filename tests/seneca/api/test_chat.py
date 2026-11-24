"""
tests/seneca/api/test_chat.py – Server-side chat: ChatService and the /chat endpoints.

The LLM is replaced by a scripted fake model and MongoDB by an in-memory
fake, so neither Ollama nor MongoDB is needed.
"""

import copy
import json
from time import sleep
from unittest.mock import MagicMock, patch

import pytest
from bson.objectid import ObjectId
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import tool_call_chunk

from seneca.api.api import api as flask_app
from seneca.api.chat import (
    MAX_TOOL_ITERATIONS,
    SYSTEM_PROMPT,
    ChatRequestError,
    ChatService,
    derive_title,
    history_to_messages,
    parse_chat_request,
)

API_KEY = "test-chat-api-key"
USER = "user-1"
CHAT_URL = "/senecaai/v1/chat"
CAPABILITIES_URL = "/senecaai/v1/chat/capabilities"
TOOL = {"name": "save_text_to_file", "description": "Save text to a file.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeLLM:
    """Chat model that streams scripted rounds of chunks and records its inputs."""

    def __init__(self, rounds, error=None):
        self.rounds = list(rounds)
        self.error = error
        self.calls = []        # messages received by each stream() call
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def stream(self, messages):
        self.calls.append(list(messages))
        chunks = self.rounds.pop(0) if self.rounds else []
        for chunk in chunks:
            yield chunk
        if self.error:
            raise self.error


def text_round(*texts):
    return [AIMessageChunk(content=t) for t in texts]


def tool_round(call_id="call-1", name="save_text_to_file", args='{"text": "hola"}', text=""):
    chunks = [AIMessageChunk(content=text)] if text else []
    chunks.append(AIMessageChunk(content="", tool_call_chunks=[
        tool_call_chunk(name=name, args=args, id=call_id, index=0)]))
    return chunks


class FakeDb:
    """In-memory replacement of MongoDatabase (only the methods used by the chat)."""

    _is_mock = True

    def __init__(self):
        self.docs = {}

    def is_connected(self):
        return True

    def add(self, user_id, messages=(), **extra):
        oid = ObjectId()
        self.docs[oid] = {"_id": oid, "user_id": user_id, "title": "Existing", "messages": list(messages), **extra}
        return str(oid)

    def doc(self, conv_id):
        return self.docs[ObjectId(conv_id)]

    def get_conversation_by_id(self, conv_id, user_id=None):
        doc = self.docs.get(ObjectId(conv_id))
        if doc is None or (user_id and doc["user_id"] != user_id):
            return None
        return copy.deepcopy(doc)

    def check_conversation_exists(self, conv_id):
        return ObjectId(conv_id) in self.docs

    def create_conversation(self, user_id, title, messages):
        oid = ObjectId()
        self.docs[oid] = {"_id": oid, "user_id": user_id, "title": title, "messages": list(messages)}
        return copy.deepcopy(self.docs[oid])

    def append_messages(self, conv_id, user_id, messages):
        self.doc(conv_id)["messages"].extend(messages)
        return True

    def set_pending_turn(self, conv_id, user_id, pending):
        self.doc(conv_id)["pending_turn"] = copy.deepcopy(pending)
        return True

    def finish_turn(self, conv_id, user_id, messages):
        doc = self.doc(conv_id)
        doc.pop("pending_turn", None)
        doc["messages"].extend(messages)
        return True


def parse_sse(body):
    """Decode an SSE body into a list of (event, data) tuples."""
    events = []
    for block in body.strip().split("\n\n"):
        lines = block.split("\n")
        name = next(line[len("event: "):] for line in lines if line.startswith("event: "))
        data = next(line[len("data: "):] for line in lines if line.startswith("data: "))
        events.append((name, json.loads(data)))
    return events


def run(service, conversation, created=False, tools=(), state=None, is_disconnected=lambda: False):
    return parse_sse("".join(service.stream_turn(conversation, USER, created, list(tools),
                                                 state=state, is_disconnected=is_disconnected)))


def user_msg(text):
    return {"role": "user", "content": text, "timestamp": "2026-01-01T10:00:00Z"}


# ---------------------------------------------------------------------------
# Request parsing and helpers
# ---------------------------------------------------------------------------

class TestParseChatRequest:
    def test_content_request(self):
        req = parse_chat_request({"content": "Hola", "tools": [TOOL]})
        assert req.content == "Hola" and req.conversation_id is None
        assert req.tools[0]["name"] == "save_text_to_file"

    @pytest.mark.parametrize("body", [
        None, [], {}, {"content": "  "}, {"content": 3},
        {"content": "a", "tool_results": [{"tool_call_id": "c", "content": "r"}], "conversation_id": "x"},
        {"tool_results": [{"tool_call_id": "c", "content": "r"}]},           # missing conversation_id
        {"conversation_id": "x", "tool_results": []},
        {"conversation_id": "x", "tool_results": [{"tool_call_id": "c", "content": 1}]},
        {"content": "a", "tools": "nope"},
        {"content": "a", "tools": [{"name": "bad name!"}]},
        {"content": "a", "tools": [TOOL, TOOL]},
        {"content": "a", "tools": [{"name": "t", "parameters": {"type": "string"}}]},
        {"content": "a", "conversation_id": 5},
    ])
    def test_invalid_bodies(self, body):
        with pytest.raises(ChatRequestError):
            parse_chat_request(body)

    def test_too_many_tools(self):
        tools = [{"name": f"t{i}"} for i in range(17)]
        with pytest.raises(ChatRequestError):
            parse_chat_request({"content": "a", "tools": tools})


def test_derive_title_truncates():
    assert derive_title("  Hola   mundo \n") == "Hola mundo"
    long_title = derive_title("x" * 100)
    assert len(long_title) <= 40 and long_title.endswith("…")


def test_history_keeps_system_prompt_and_last_messages():
    stored = [user_msg(f"m{i}") for i in range(10)]
    messages = history_to_messages(stored, max_messages=3)
    assert isinstance(messages[0], SystemMessage) and messages[0].content == SYSTEM_PROMPT
    assert [m.content for m in messages[1:]] == ["m7", "m8", "m9"]


# ---------------------------------------------------------------------------
# ChatService
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return FakeDb()


def make_service(db, llm):
    return ChatService(db, llm_factory=lambda: llm, max_history_messages=50, provider="ollama", model="m")


class TestChatService:
    def test_new_conversation_streams_and_stores_both_messages(self, db):
        llm = FakeLLM([text_round("Ho", "la")])
        service = make_service(db, llm)
        req = parse_chat_request({"content": "Saluda"})

        conversation, created = service.start_turn(USER, req, None)
        events = run(service, conversation, created)

        assert [e for e, _ in events] == ["conversation", "token", "token", "done"]
        assert events[0][1] == {"id": str(conversation["_id"]), "title": "Saluda", "created": True}
        assert "".join(d["text"] for e, d in events if e == "token") == "Hola"
        stored = db.doc(str(conversation["_id"]))["messages"]
        assert [(m["role"], m["content"]) for m in stored] == [("user", "Saluda"), ("assistant", "Hola")]
        assert events[-1][1]["message"]["content"] == "Hola"
        # The model received the system prompt and the user message
        assert isinstance(llm.calls[0][0], SystemMessage)
        assert isinstance(llm.calls[0][-1], HumanMessage) and llm.calls[0][-1].content == "Saluda"

    def test_existing_conversation_includes_history(self, db):
        conv_id = db.add(USER, [user_msg("Antes"), {"role": "assistant", "content": "Vale",
                                                    "timestamp": "2026-01-01T10:00:01Z"}])
        llm = FakeLLM([text_round("Ok")])
        service = make_service(db, llm)

        conversation, created = service.start_turn(USER, parse_chat_request({"content": "Ahora"}),
                                                   db.get_conversation_by_id(conv_id, USER))
        events = run(service, conversation, created)

        assert created is False and events[0][1]["created"] is False
        assert [m.content for m in llm.calls[0][1:]] == ["Antes", "Vale", "Ahora"]
        assert [m["content"] for m in db.doc(conv_id)["messages"]] == ["Antes", "Vale", "Ahora", "Ok"]

    def test_empty_reply_stores_no_assistant_message(self, db):
        service = make_service(db, FakeLLM([[]]))
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Hola"}), None)
        events = run(service, conversation)
        assert events[-1] == ("done", {"message": None})
        assert len(db.doc(str(conversation["_id"]))["messages"]) == 1

    def test_tool_call_pauses_the_turn(self, db):
        llm = FakeLLM([tool_round(text="Voy. ")])
        service = make_service(db, llm)
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Guarda"}), None)

        events = run(service, conversation, tools=[TOOL])

        assert events[-1] == ("tool_calls", {"tool_calls": [
            {"id": "call-1", "name": "save_text_to_file", "args": {"text": "hola"}}]})
        assert llm.bound_tools[0]["function"]["name"] == "save_text_to_file"
        doc = db.doc(str(conversation["_id"]))
        assert doc["pending_turn"]["awaiting"] == ["call-1"]
        assert doc["pending_turn"]["reply"] == "Voy. "
        assert len(doc["messages"]) == 1  # nothing stored until the turn ends

    def test_tool_results_resume_the_turn(self, db):
        llm = FakeLLM([tool_round(text="Voy. "), text_round("Hecho.")])
        service = make_service(db, llm)
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Guarda"}), None)
        conv_id = str(conversation["_id"])
        run(service, conversation, tools=[TOOL])

        stored = db.get_conversation_by_id(conv_id, USER)
        state = service.resume_state(stored, [{"tool_call_id": "call-1", "content": "/tmp/x.txt"}])
        events = run(service, stored, tools=[TOOL], state=state)

        assert [e for e, _ in events] == ["conversation", "token", "done"]
        second_call = llm.calls[1]
        assert isinstance(second_call[-1], ToolMessage) and second_call[-1].content == "/tmp/x.txt"
        assert second_call[-2].tool_calls[0]["id"] == "call-1"
        doc = db.doc(conv_id)
        assert "pending_turn" not in doc
        # The stored reply is everything the user saw, across both rounds
        assert doc["messages"][-1]["content"] == "Voy. Hecho."

    def test_resume_without_pending_turn(self, db):
        conv_id = db.add(USER, [user_msg("Hola")])
        with pytest.raises(LookupError):
            ChatService.resume_state(db.get_conversation_by_id(conv_id), [{"tool_call_id": "c", "content": "r"}])

    def test_resume_with_wrong_ids(self, db):
        conv_id = db.add(USER, [user_msg("Hola")],
                         pending_turn={"messages": [], "reply": "", "iterations": 1, "awaiting": ["c1"]})
        with pytest.raises(ChatRequestError):
            ChatService.resume_state(db.get_conversation_by_id(conv_id), [{"tool_call_id": "c2", "content": "r"}])

    def test_missing_tool_call_ids_are_generated(self, db):
        llm = FakeLLM([tool_round(call_id=None)])
        service = make_service(db, llm)
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Guarda"}), None)
        events = run(service, conversation, tools=[TOOL])
        call_id = events[-1][1]["tool_calls"][0]["id"]
        assert call_id.startswith("call_")
        assert db.doc(str(conversation["_id"]))["pending_turn"]["awaiting"] == [call_id]

    def test_tool_calls_are_ignored_without_tools(self, db):
        service = make_service(db, FakeLLM([tool_round(text="Texto")]))
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Hola"}), None)
        events = run(service, conversation)
        assert events[-1][0] == "done"

    def test_tool_round_limit(self, db):
        service = make_service(db, FakeLLM([tool_round(text="Otra vez")]))
        conv_id = db.add(USER, [user_msg("Hola")])
        stored = db.get_conversation_by_id(conv_id)
        state = ChatService.resume_state(
            {**stored, "pending_turn": {"messages": [], "reply": "", "iterations": MAX_TOOL_ITERATIONS,
                                        "awaiting": ["c1"]}},
            [{"tool_call_id": "c1", "content": "r"}])
        events = run(service, stored, tools=[TOOL], state=state)
        assert events[-1][0] == "done"
        assert db.doc(conv_id)["messages"][-1]["content"] == "Otra vez"

    def test_new_message_closes_an_abandoned_tool_turn(self, db):
        conv_id = db.add(USER, [user_msg("Guarda")],
                         pending_turn={"messages": [], "reply": "Voy. ", "iterations": 1, "awaiting": ["c1"]})
        service = make_service(db, FakeLLM([text_round("Ok")]))

        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Déjalo"}),
                                             db.get_conversation_by_id(conv_id, USER))
        run(service, conversation)

        contents = [m["content"] for m in db.doc(conv_id)["messages"]]
        assert contents == ["Guarda", "Voy. ", "Déjalo", "Ok"]
        assert "pending_turn" not in db.doc(conv_id)

    def test_llm_error_sends_error_event_and_keeps_partial_reply(self, db):
        service = make_service(db, FakeLLM([text_round("Parcial")], error=RuntimeError("model crashed")))
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Hola"}), None)
        events = run(service, conversation)
        assert events[-1] == ("error", {"error": "model crashed"})
        assert db.doc(str(conversation["_id"]))["messages"][-1]["content"] == "Parcial"

    def test_llm_creation_error_is_reported(self, db):
        def broken_factory():
            raise ValueError("Unknown LLM_PROVIDER: 'x'")
        service = ChatService(db, llm_factory=broken_factory)
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Hola"}), None)
        events = run(service, conversation)
        assert events[-1] == ("error", {"error": "Unknown LLM_PROVIDER: 'x'"})

    def test_client_disconnect_stops_and_stores_partial_reply(self, db):
        service = make_service(db, FakeLLM([text_round("Uno ", "dos ", "tres")]))
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Cuenta"}), None)
        checks = iter([False, False, True])

        events = run(service, conversation, is_disconnected=lambda: next(checks))

        assert [e for e, _ in events] == ["conversation", "token", "token"]
        assert db.doc(str(conversation["_id"]))["messages"][-1]["content"] == "Uno dos "

    def test_closing_the_generator_stores_partial_reply(self, db):
        # waitress closes the response iterator when the client goes away
        service = make_service(db, FakeLLM([text_round("Uno ", "dos ", "tres")]))
        conversation, _ = service.start_turn(USER, parse_chat_request({"content": "Cuenta"}), None)
        stream = service.stream_turn(conversation, USER, True, [])
        next(stream)  # conversation
        next(stream)  # "Uno "
        stream.close()
        assert db.doc(str(conversation["_id"]))["messages"][-1]["content"] == "Uno "

    def test_capabilities(self, db):
        llm = FakeLLM([])
        service = make_service(db, llm)
        assert service.capabilities() == {"provider": "ollama", "model": "m", "tool_calling": True}

    def test_capabilities_when_llm_cannot_be_created(self, db):
        def broken_factory():
            raise ValueError("no key")
        service = ChatService(db, llm_factory=broken_factory, provider="openai", model="gpt")
        assert service.capabilities()["tool_calling"] is False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    mock_config = MagicMock()
    mock_config.seneca_ai_api_key = API_KEY
    with patch("seneca.api.api.config", new=mock_config):
        from seneca.api.api import limiter
        limiter.enabled = False
        with flask_app.test_client() as test_client:
            yield test_client


@pytest.fixture(autouse=True)
def delay_to_avoid_too_many_request_per_second():
    sleep(0.01)


@pytest.fixture
def chat_env(db):
    """Patch the API's database and chat service; yields (db, set_llm)."""
    holder = {"llm": FakeLLM([text_round("Hola")])}
    service = ChatService(db, llm_factory=lambda: holder["llm"], provider="ollama", model="m")

    def set_llm(llm):
        holder["llm"] = llm

    with patch("seneca.api.api.db_client", new=db), patch("seneca.api.api.chat_service", new=service):
        yield db, set_llm


def headers(user=USER):
    return {"X-SENECA-AI-API-KEY": API_KEY, "X-SENECA-AI-USER-ID": user}


class TestChatEndpoint:
    def test_requires_authentication(self, client, chat_env):
        assert client.post(CHAT_URL, json={"content": "Hola"}).status_code == 401

    def test_new_conversation(self, client, chat_env):
        db, _ = chat_env
        response = client.post(CHAT_URL, json={"content": "Hola"}, headers=headers())

        assert response.status_code == 200
        assert response.mimetype == "text/event-stream"
        events = parse_sse(response.get_data(as_text=True))
        assert [e for e, _ in events] == ["conversation", "token", "done"]
        conv_id = events[0][1]["id"]
        assert db.doc(conv_id)["user_id"] == USER
        assert [m["role"] for m in db.doc(conv_id)["messages"]] == ["user", "assistant"]

    def test_invalid_body(self, client, chat_env):
        response = client.post(CHAT_URL, json={"content": ""}, headers=headers())
        assert response.status_code == 400

    def test_invalid_conversation_id(self, client, chat_env):
        response = client.post(CHAT_URL, json={"content": "Hola", "conversation_id": "nope"}, headers=headers())
        assert response.status_code == 400

    def test_unknown_conversation(self, client, chat_env):
        response = client.post(CHAT_URL, json={"content": "Hola", "conversation_id": str(ObjectId())},
                               headers=headers())
        assert response.status_code == 404

    def test_conversation_of_another_user(self, client, chat_env):
        db, _ = chat_env
        conv_id = db.add("someone-else", [user_msg("Privado")])
        response = client.post(CHAT_URL, json={"content": "Hola", "conversation_id": conv_id}, headers=headers())
        assert response.status_code == 403
        assert len(db.doc(conv_id)["messages"]) == 1

    def test_tool_round_trip(self, client, chat_env):
        db, set_llm = chat_env
        set_llm(FakeLLM([tool_round(), text_round("Guardado.")]))

        first = parse_sse(client.post(CHAT_URL, json={"content": "Guarda hola", "tools": [TOOL]},
                                      headers=headers()).get_data(as_text=True))
        assert first[-1][0] == "tool_calls"
        conv_id = first[0][1]["id"]

        response = client.post(CHAT_URL, headers=headers(), json={
            "conversation_id": conv_id, "tools": [TOOL],
            "tool_results": [{"tool_call_id": "call-1", "content": "ok"}]})
        second = parse_sse(response.get_data(as_text=True))

        assert [e for e, _ in second] == ["conversation", "token", "done"]
        assert db.doc(conv_id)["messages"][-1]["content"] == "Guardado."

    def test_tool_results_without_pending_turn(self, client, chat_env):
        db, _ = chat_env
        conv_id = db.add(USER, [user_msg("Hola")])
        response = client.post(CHAT_URL, headers=headers(), json={
            "conversation_id": conv_id, "tool_results": [{"tool_call_id": "c", "content": "r"}]})
        assert response.status_code == 409

    def test_tool_results_with_wrong_ids(self, client, chat_env):
        db, _ = chat_env
        conv_id = db.add(USER, [user_msg("Hola")],
                         pending_turn={"messages": [], "reply": "", "iterations": 1, "awaiting": ["c1"]})
        response = client.post(CHAT_URL, headers=headers(), json={
            "conversation_id": conv_id, "tool_results": [{"tool_call_id": "zz", "content": "r"}]})
        assert response.status_code == 400

    def test_pending_turn_is_not_exposed(self, client, chat_env):
        db, _ = chat_env
        conv_id = db.add(USER, [user_msg("Hola")],
                         pending_turn={"messages": [], "reply": "", "iterations": 1, "awaiting": ["c1"]})
        response = client.get(f"/senecaai/v1/conversations/{conv_id}", headers=headers())
        assert response.status_code == 200
        assert "pending_turn" not in response.get_json()

    def test_capabilities(self, client, chat_env):
        response = client.get(CAPABILITIES_URL, headers=headers())
        assert response.status_code == 200
        assert response.get_json() == {"provider": "ollama", "model": "m", "tool_calling": True}

    def test_capabilities_require_authentication(self, client, chat_env):
        assert client.get(CAPABILITIES_URL).status_code == 401
