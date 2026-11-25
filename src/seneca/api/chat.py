"""
src/seneca/api/chat.py – Server-side chat for the ``/senecaai/v1/chat`` endpoint.

The desktop app (or any other client) sends the user's message; the API
builds the prompt from the conversation stored in MongoDB, calls the LLM
selected with ``LLM_PROVIDER`` and streams the reply back as Server-Sent
Events (SSE), persisting both the user message and the reply.

Tools are executed by the client
--------------------------------
Tools such as "open the reply in Notepad" act on the user's computer, so the
server cannot run them.  The client sends their JSON-schema definitions with
each request; when the model asks for a tool, the server:

1. stores the turn state in ``conversation.pending_turn`` (MongoDB),
2. sends a ``tool_calls`` event and ends the stream,

and the client runs the tools and sends their results in a new request
(``tool_results``), which resumes the turn.  Keeping the state in MongoDB
makes the round trip independent of the server process/thread.

SSE events
----------
``conversation``  ``{"id", "title", "created"}`` – always the first event.
``token``         ``{"text"}`` – a chunk of the reply.
``tool_calls``    ``{"tool_calls": [{"id", "name", "args"}]}`` – run them and
                  send the results; the stream ends after this event.
``done``          ``{"message": {...} | null}`` – the stored assistant message.
``error``         ``{"error"}`` – the turn failed; the stream ends.

See docs/chat-api.md for the full protocol.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    messages_from_dict,
    messages_to_dict,
)

from seneca.memory.service import MemoryService, format_summary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres Seneca-AI, un asistente europeo de código abierto, "
    "diseñado para apoyar y empoderar a las personas, nunca para "
    "reemplazarlas. Responde siempre con claridad, respeto y rigor. "
    "Adapta el idioma de la respuesta al del usuario."
)

# Safety limit of tool-calling rounds within a single turn, to guard
# against a model that keeps requesting tools indefinitely.
MAX_TOOL_ITERATIONS = 5

# Limits on the client-provided input
MAX_CONTENT_LENGTH = 32_000
MAX_TOOLS = 16
MAX_TOOL_DESCRIPTION_LENGTH = 2_000
MAX_TOOL_RESULT_LENGTH = 32_000
TITLE_MAX_LENGTH = 40
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ChatRequestError(ValueError):
    """The body of a chat request is invalid (HTTP 400)."""


# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------

def _create_openai_llm(cfg) -> BaseChatModel:
    from langchain_openai import ChatOpenAI  # noqa: PLC0415
    return ChatOpenAI(model=cfg.openai_model, api_key=cfg.openai_api_key, streaming=True)


def _create_ollama_llm(cfg) -> BaseChatModel:
    from langchain_ollama import ChatOllama  # noqa: PLC0415
    return ChatOllama(model=cfg.ollama_model, base_url=cfg.ollama_base_url)


def _create_anthropic_llm(cfg) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
    return ChatAnthropic(model=cfg.anthropic_model, api_key=cfg.anthropic_api_key, streaming=True)


# provider name -> (factory, config attribute holding the model name)
_LLM_PROVIDERS: Dict[str, tuple[Callable[[Any], BaseChatModel], str]] = {
    "openai": (_create_openai_llm, "openai_model"),
    "ollama": (_create_ollama_llm, "ollama_model"),
    "anthropic": (_create_anthropic_llm, "anthropic_model"),
}


def build_llm(cfg) -> BaseChatModel:
    """Instantiate the LLM selected by ``cfg.llm_provider``."""
    provider = cfg.llm_provider.lower()
    if provider not in _LLM_PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'")
    factory, _ = _LLM_PROVIDERS[provider]
    return factory(cfg)


def model_name(cfg) -> str:
    """Name of the model used by the configured provider."""
    provider = cfg.llm_provider.lower()
    if provider not in _LLM_PROVIDERS:
        return ""
    return getattr(cfg, _LLM_PROVIDERS[provider][1], "")


def supports_tool_calling(llm: BaseChatModel) -> bool:
    """Best-effort check of whether *llm* supports tool calling.

    Order of precedence:
      1. Explicit capability metadata (``llm.profile.tool_calling``), if any.
      2. Known provider-specific boolean attributes.
      3. A non-invasive binding probe: ``bind_tools()`` with a dummy tool.
         Merely checking that the method exists gives false positives,
         because most chat models inherit it.
    """
    profile = getattr(llm, "profile", None)
    tool_flag = getattr(profile, "tool_calling", None) if profile is not None else None
    if isinstance(tool_flag, bool):
        return tool_flag

    for attr in ("supports_tool_calling", "tool_calling", "function_calling"):
        value = getattr(llm, attr, None)
        if isinstance(value, bool):
            return value

    bind_tools = getattr(llm, "bind_tools", None)
    if not callable(bind_tools):
        return False
    try:
        bind_tools([{"name": "probe_tool", "description": "probe",
                     "parameters": {"type": "object", "properties": {}}}])
        return True
    except NotImplementedError:
        return False
    except Exception as exc:  # noqa: BLE001 – any failure means "not supported"
        logger.debug("Tool probe failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

@dataclass
class ChatRequest:
    """A validated ``POST /senecaai/v1/chat`` body."""

    conversation_id: Optional[str] = None
    content: Optional[str] = None
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: Optional[List[Dict[str, str]]] = None


def _parse_tools(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ChatRequestError("'tools' must be a list.")
    if len(raw) > MAX_TOOLS:
        raise ChatRequestError(f"At most {MAX_TOOLS} tools are allowed.")

    tools, names = [], set()
    for tool in raw:
        if not isinstance(tool, dict):
            raise ChatRequestError("Each tool must be an object.")
        name = tool.get("name")
        if not isinstance(name, str) or not _TOOL_NAME_RE.match(name):
            raise ChatRequestError("Each tool needs a 'name' of 1-64 letters, digits, '_' or '-'.")
        if name in names:
            raise ChatRequestError(f"Duplicated tool name: '{name}'.")
        description = tool.get("description", "")
        if not isinstance(description, str) or len(description) > MAX_TOOL_DESCRIPTION_LENGTH:
            raise ChatRequestError(
                f"Tool 'description' must be a string of at most {MAX_TOOL_DESCRIPTION_LENGTH} characters.")
        parameters = tool.get("parameters", {"type": "object", "properties": {}})
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            raise ChatRequestError("Tool 'parameters' must be a JSON schema of type 'object'.")
        names.add(name)
        tools.append({"name": name, "description": description, "parameters": parameters})
    return tools


def _parse_tool_results(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ChatRequestError("'tool_results' must be a non-empty list.")
    results = []
    for item in raw:
        if not isinstance(item, dict):
            raise ChatRequestError("Each tool result must be an object.")
        call_id, content = item.get("tool_call_id"), item.get("content")
        if not isinstance(call_id, str) or not call_id:
            raise ChatRequestError("Each tool result needs a 'tool_call_id'.")
        if not isinstance(content, str):
            raise ChatRequestError("Tool result 'content' must be a string.")
        results.append({"tool_call_id": call_id, "content": content[:MAX_TOOL_RESULT_LENGTH]})
    return results


def parse_chat_request(data: Any) -> ChatRequest:
    """Validate the JSON body of a chat request.

    Exactly one of ``content`` (a new user message) or ``tool_results``
    (resume a turn waiting for tools) must be present.
    """
    if not isinstance(data, dict):
        raise ChatRequestError("The request body must be a JSON object.")

    conversation_id = data.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise ChatRequestError("'conversation_id' must be a string.")

    has_content = data.get("content") is not None
    has_results = data.get("tool_results") is not None
    if has_content == has_results:
        raise ChatRequestError("Provide either 'content' or 'tool_results'.")

    request = ChatRequest(conversation_id=conversation_id or None, tools=_parse_tools(data.get("tools")))

    if has_content:
        content = data["content"]
        if not isinstance(content, str) or not content.strip():
            raise ChatRequestError("'content' must be a non-empty string.")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ChatRequestError(f"'content' must not exceed {MAX_CONTENT_LENGTH} characters.")
        request.content = content
    else:
        if not request.conversation_id:
            raise ChatRequestError("'conversation_id' is required with 'tool_results'.")
        request.tool_results = _parse_tool_results(data["tool_results"])
    return request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_timestamp() -> str:
    """Current time as an ISO 8601 UTC string, the format stored in messages."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_message(role: str, content: str) -> Dict[str, str]:
    """A message in the format stored in ``conversation.messages``."""
    return {"role": role, "content": content, "timestamp": utc_timestamp()}


def derive_title(content: str) -> str:
    """Conversation title: the first user message, truncated."""
    raw = " ".join(content.split())
    return raw[: TITLE_MAX_LENGTH - 3] + "…" if len(raw) > TITLE_MAX_LENGTH else raw


def sse(event: str, data: Dict[str, Any]) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def history_to_messages(stored: List[Dict[str, Any]], max_messages: int,
                        context: str = "") -> List[BaseMessage]:
    """System prompt + the last *max_messages* stored user/assistant messages.

    *context* (memory, summary of older messages) is appended to the system
    prompt. It is one system message because some providers (Anthropic)
    accept a single one, at the start.
    """
    role_map = {"user": HumanMessage, "assistant": AIMessage}
    recent = stored[-max_messages:] if max_messages > 0 else stored
    system = f"{SYSTEM_PROMPT}\n\n{context}" if context else SYSTEM_PROMPT
    messages: List[BaseMessage] = [SystemMessage(content=system)]
    messages.extend(role_map[m["role"]](content=m["content"]) for m in recent if m.get("role") in role_map)
    return messages


def _openai_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "function", "function": tool}


# ---------------------------------------------------------------------------
# Turn execution
# ---------------------------------------------------------------------------

@dataclass
class TurnState:
    """Progress of a turn; persisted as ``pending_turn`` while waiting for tools."""

    # Messages of this turn after the stored history: assistant tool-call
    # messages and the tool results
    messages: List[BaseMessage] = field(default_factory=list)
    # Text already streamed to the client in this turn
    reply: str = ""
    iterations: int = 0
    # Ids of the tool calls whose results the client must send
    awaiting: List[str] = field(default_factory=list)

    def to_document(self) -> Dict[str, Any]:
        return {
            "messages": messages_to_dict(self.messages),
            "reply": self.reply,
            "iterations": self.iterations,
            "awaiting": self.awaiting,
        }

    @classmethod
    def from_document(cls, doc: Optional[Dict[str, Any]]) -> "TurnState":
        if not doc:
            return cls()
        return cls(
            messages=messages_from_dict(doc.get("messages", [])),
            reply=doc.get("reply", ""),
            iterations=doc.get("iterations", 0),
            awaiting=list(doc.get("awaiting", [])),
        )


class ClientDisconnected(Exception):
    """The client closed the connection (the user pressed "stop")."""


class ChatService:
    """Runs chat turns against the configured LLM and persists them.

    Parameters
    ----------
    db:
        :class:`seneca.api.database.MongoDatabase` (or a compatible fake).
    llm_factory:
        Returns a new chat model; called once per turn.
    max_history_messages:
        Stored messages sent to the model as context (most recent ones).
    memory:
        Optional :class:`MemoryService`: related turns of the user's other
        conversations are added to the prompt.
    """

    def __init__(self, db, llm_factory: Callable[[], BaseChatModel], max_history_messages: int = 50,
                 provider: str = "", model: str = "", memory: Optional[MemoryService] = None) -> None:
        self._db = db
        self._memory = memory
        self._llm_factory = llm_factory
        self._max_history_messages = max_history_messages
        self._provider = provider
        self._model = model
        self._tool_calling: Optional[bool] = None

    # -- capabilities --------------------------------------------------------

    def capabilities(self) -> Dict[str, Any]:
        """Provider, model and tool-calling support (cached after the first probe)."""
        if self._tool_calling is None:
            try:
                self._tool_calling = supports_tool_calling(self._llm_factory())
            except Exception as exc:  # noqa: BLE001 – report "no tools" instead of failing
                logger.error("Could not create the LLM to check its capabilities: %s", exc)
                return {"provider": self._provider, "model": self._model, "tool_calling": False}
        return {"provider": self._provider, "model": self._model, "tool_calling": self._tool_calling}

    # -- prompt context --------------------------------------------------------

    def prompt_context(self, conversation: Dict[str, Any], user_id: str) -> str:
        """Extra system-prompt context: summary of older messages and memory."""
        parts = []
        stored = conversation.get("messages", [])
        if 0 < self._max_history_messages < len(stored):
            # The oldest messages do not fit: the worker's running summary stands in for them
            parts.append(format_summary((conversation.get("memory") or {}).get("summary", "")))
        if self._memory is not None:
            query = next((m.get("content", "") for m in reversed(stored) if m.get("role") == "user"), "")
            parts.append(self._memory.context(user_id, query, exclude_conversation_id=str(conversation["_id"])))
        return "\n\n".join(part for part in parts if part)

    # -- turn lifecycle ------------------------------------------------------

    def close_pending_turn(self, conversation: Dict[str, Any], user_id: str) -> None:
        """Finish a turn abandoned while waiting for tools, keeping the text already shown."""
        state = TurnState.from_document(conversation.get("pending_turn"))
        reply = [new_message("assistant", state.reply)] if state.reply.strip() else []
        self._db.finish_turn(str(conversation["_id"]), user_id, reply)
        conversation.pop("pending_turn", None)
        conversation["messages"] = conversation.get("messages", []) + reply

    def start_turn(self, user_id: str, request: ChatRequest,
                   conversation: Optional[Dict[str, Any]]) -> tuple[Dict[str, Any], bool]:
        """Store the user message (creating the conversation if needed).

        Returns the conversation document, including the new message, and
        whether it was created.
        """
        user_message = new_message("user", request.content)
        if conversation is None:
            conversation = self._db.create_conversation(user_id, derive_title(request.content), [user_message])
            return conversation, True

        if conversation.get("pending_turn"):
            self.close_pending_turn(conversation, user_id)
        self._db.append_messages(str(conversation["_id"]), user_id, [user_message])
        conversation["messages"] = conversation.get("messages", []) + [user_message]
        return conversation, False

    @staticmethod
    def resume_state(conversation: Dict[str, Any], tool_results: List[Dict[str, str]]) -> TurnState:
        """Turn state of a conversation waiting for tools, with the client's results added.

        Raises :class:`LookupError` if no turn is waiting for tools and
        :class:`ChatRequestError` if the results do not match the calls.
        """
        if not conversation.get("pending_turn"):
            raise LookupError("No tool calls are awaiting results in this conversation.")
        state = TurnState.from_document(conversation["pending_turn"])
        received = [r["tool_call_id"] for r in tool_results]
        if sorted(received) != sorted(state.awaiting):
            raise ChatRequestError(
                f"Expected results for tool calls {sorted(state.awaiting)}, got {sorted(received)}.")
        state.messages.extend(ToolMessage(content=r["content"], tool_call_id=r["tool_call_id"])
                              for r in tool_results)
        state.awaiting = []
        return state

    def stream_turn(self, conversation: Dict[str, Any], user_id: str, created: bool,
                    tools: List[Dict[str, Any]], state: Optional[TurnState] = None,
                    is_disconnected: Callable[[], bool] = lambda: False) -> Iterator[str]:
        """Run the LLM for a stored conversation and yield SSE-formatted events.

        The reply is persisted when the turn ends, even if it ends early
        because the client disconnected or the LLM failed.
        """
        conv_id = str(conversation["_id"])
        state = state or TurnState()
        yield sse("conversation", {"id": conv_id, "title": conversation.get("title", ""), "created": created})

        finished = False

        def finish() -> Optional[Dict[str, str]]:
            nonlocal finished
            finished = True
            message = new_message("assistant", state.reply) if state.reply.strip() else None
            self._db.finish_turn(conv_id, user_id, [message] if message else [])
            return message

        try:
            llm = self._llm_factory()
            if tools:
                llm = llm.bind_tools([_openai_tool(t) for t in tools])
            messages = (history_to_messages(conversation.get("messages", []), self._max_history_messages,
                                            self.prompt_context(conversation, user_id))
                        + state.messages)

            while True:
                aggregate = None
                for chunk in llm.stream(messages):
                    if is_disconnected():
                        raise ClientDisconnected()
                    aggregate = chunk if aggregate is None else aggregate + chunk
                    text = chunk.text
                    if text:
                        state.reply += text
                        yield sse("token", {"text": text})

                tool_calls = list(getattr(aggregate, "tool_calls", None) or [])
                if not tool_calls or not tools:
                    break
                if state.iterations >= MAX_TOOL_ITERATIONS:
                    logger.warning("Reached the limit of %d tool-calling rounds in conversation %s.",
                                   MAX_TOOL_ITERATIONS, conv_id)
                    break

                # Some providers omit the ids; the client needs them to send the results
                for call in tool_calls:
                    call["id"] = call.get("id") or f"call_{uuid.uuid4().hex}"
                state.iterations += 1
                state.messages.append(AIMessage(content=aggregate.content, tool_calls=tool_calls))
                state.awaiting = [call["id"] for call in tool_calls]
                self._db.set_pending_turn(conv_id, user_id, state.to_document())
                finished = True
                yield sse("tool_calls", {"tool_calls": [
                    {"id": c["id"], "name": c["name"], "args": c.get("args", {})} for c in tool_calls]})
                return

            message = finish()
            yield sse("done", {"message": message})

        except (ClientDisconnected, GeneratorExit):
            # GeneratorExit: the server closed the stream because the client left
            logger.info("Client disconnected from conversation %s; storing the partial reply.", conv_id)
            if not finished:
                finish()
            return
        except Exception as exc:  # noqa: BLE001 – reported to the client as an event
            logger.exception("Chat turn failed in conversation %s: %s", conv_id, exc)
            if not finished:
                finish()
            yield sse("error", {"error": _error_message(exc)})


def _error_message(exc: Exception) -> str:
    """User-facing message of an LLM error.

    Several SDKs (OpenAI, Anthropic) attach a structured ``body`` with a
    ``"message"`` field to their exceptions; prefer it when present.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    return str(exc) or exc.__class__.__name__
