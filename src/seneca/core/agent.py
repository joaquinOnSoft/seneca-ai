"""
src/seneca/core/agent.py – LangChain-backed AI agent for Seneca.

Supports multiple LLM providers (OpenAI, Ollama, Anthropic) chosen
via the ``LLM_PROVIDER`` environment variable.  The agent streams
its reply token-by-token, calling *on_token* for each chunk so the
UI can display text progressively.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, List, Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import StructuredTool

from seneca.core.conversation import Conversation, Role
from seneca.utils.config import config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Eres Seneca-AI, un asistente europeo de código abierto, "
    "diseñado para apoyar y empoderar a las personas, nunca para "
    "reemplazarlas. Responde siempre con claridad, respeto y rigor. "
    "Adapta el idioma de la respuesta al del usuario."
)

# Safety limit for tool-calling rounds within a single stream_reply() call,
# to guard against a model that keeps requesting tools indefinitely.
_MAX_TOOL_ITERATIONS = 5

# Define a dictionary to map provider names to their respective factory functions
_LLM_PROVIDER_FACTORIES: Dict[str, Callable[[], BaseChatModel]] = {}

def _register_llm_provider(name: str, factory: Callable[[], BaseChatModel]):
    """Register an LLM provider factory function."""
    _LLM_PROVIDER_FACTORIES[name.lower()] = factory

# Register OpenAI
def _create_openai_llm() -> BaseChatModel:
    from langchain_openai import ChatOpenAI  # noqa: PLC0415
    return ChatOpenAI(
        model=config.openai_model,
        api_key=config.openai_api_key,
        streaming=True,
    )
_register_llm_provider("openai", _create_openai_llm)

# Register Ollama
def _create_ollama_llm() -> BaseChatModel:
    from langchain_ollama import ChatOllama  # noqa: PLC0415
    return ChatOllama(
        model=config.ollama_model,
        base_url=config.ollama_base_url,
    )
_register_llm_provider("ollama", _create_ollama_llm)

# Register Anthropic
def _create_anthropic_llm() -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
    return ChatAnthropic(
        model = config.anthropic_model,
        api_key=config.anthropic_api_key,
        streaming=True,
    )
_register_llm_provider("anthropic", _create_anthropic_llm)


def _build_llm() -> BaseChatModel:
    """Instantiate the correct LLM based on *config.llm_provider*."""
    provider_name = config.llm_provider.lower()
    factory = _LLM_PROVIDER_FACTORIES.get(provider_name)

    if factory:
        return factory()

    raise ValueError(f"Unknown LLM_PROVIDER: '{provider_name}'")


def _conv_to_messages(conv: Conversation) -> List[BaseMessage]:
    """Convert a :class:`Conversation` into LangChain message objects."""
    msgs: List[BaseMessage] = [SystemMessage(content=_SYSTEM_PROMPT)]
    role_map = {Role.USER: HumanMessage, Role.ASSISTANT: AIMessage}
    for m in conv.messages:
        msgs.append(role_map[m.role](content=m.content))
    return msgs


def _get_error_msg(exc: Exception) -> str:
    """
    Extract a user-facing message from an exception.

    Several LLM SDKs (e.g. the OpenAI/Anthropic clients) attach a
    structured ``body`` dict to their exceptions with a ``"message"``
    field; prefer that when present, otherwise fall back to ``str(exc)``.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and "message" in body:
        try:
            return str(body["message"])
        except TypeError:
            pass
    return str(exc)


class SenecaAgent:
    """
    Thin wrapper around a LangChain chat model.

    Exposes :meth:`stream_reply` which runs inference in a daemon
    thread, delivering each token via a callback.
    """

    def __init__(self) -> None:
        self._llm: BaseChatModel | None = None
        self._cancel_event = threading.Event()
        self._tools: List[Any] = []

    def _get_llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = _build_llm()
            if self._tools:
                self._llm = self._llm.bind_tools(self._tools)
        return self._llm

    def supports_tools(self) -> bool:
        """
        Robust check for tool-calling support in an LLM.

        Order of precedence:
          1. Explicit capability metadata (``llm.profile.tool_calling``), if any.
          2. Known provider-specific boolean attributes.
          3. A real (non-invasive) binding probe: actually call
             ``bind_tools()`` with a dummy tool and see whether it
             succeeds. This is authoritative because most
             ``BaseChatModel`` subclasses expose a ``bind_tools`` method
             regardless of whether the underlying provider truly
             supports tool calling — merely checking for the attribute's
             existence produces false positives.
        """
        try:
            llm = self._get_llm()

            # --- 1. Explicit capability metadata (best case) ---
            profile = getattr(llm, "profile", None)
            if profile is not None:
                tool_flag = getattr(profile, "tool_calling", None)
                if isinstance(tool_flag, bool):
                    return tool_flag

            # --- 2. Known provider-specific attributes ---
            provider_flags = (
                "supports_tool_calling",
                "tool_calling",
                "function_calling",  # OpenAI-style naming
            )
            for attr in provider_flags:
                val = getattr(llm, attr, None)
                if isinstance(val, bool):
                    return val

            # --- 3. Behavioral probe: try a real (non-invasive) bind ---
            bind_tools = getattr(llm, "bind_tools", None)
            if not callable(bind_tools):
                return False

            try:
                dummy_tool = {
                    "name": "test_tool",
                    "description": "test",
                    "parameters": {"type": "object", "properties": {}},
                }
                bind_tools([dummy_tool])
                return True
            except NotImplementedError:
                return False
            except Exception as probe_err:
                logger.debug("Tool probe failed: %s", probe_err)
                return False

        except Exception as e:
            logger.error("Error checking tool support: %s", e)
            return False

    def add_tool(self, tool_func: Callable) -> None:
        """Add a tool to the LLM."""
        if not self.supports_tools():
            logger.warning("Attempted to add tool to a model that doesn't support tool calling.")
            return

        # Wrap the function as a LangChain StructuredTool if it's not already
        name = getattr(tool_func, "name", tool_func.__name__)

        # Avoid duplicates
        for t in self._tools:
            if t.name == name:
                return

        if not hasattr(tool_func, "name"):
            tool = StructuredTool.from_function(
                func=tool_func,
                name=name,
                description=tool_func.__doc__ or f"Execute {name}",
            )
        else:
            tool = tool_func

        self._tools.append(tool)
        # Re-initialize LLM with new tools on next use
        self._llm = None

    def remove_tool(self, tool_func: Callable) -> None:
        """Remove a tool from the LLM."""
        name = getattr(tool_func, "name", tool_func.__name__)
        self._tools = [t for t in self._tools if t.name != name]
        # Re-initialize LLM
        self._llm = None

    def _run_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        assistant_reply: str,
        messages: List[BaseMessage],
    ) -> None:
        """
        Execute every requested tool call, appending the assistant's
        tool-call turn and each tool's result (as a ``ToolMessage``) to
        *messages* in place, so the next LLM call can use them.
        """
        messages.append(AIMessage(content=assistant_reply, tool_calls=tool_calls))

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call.get("id", tool_name)

            tool = next((t for t in self._tools if t.name == tool_name), None)
            if tool is None:
                result_content = f"Error: tool '{tool_name}' not found."
                logger.warning("Model requested unknown tool '%s'.", tool_name)
            else:
                try:
                    result_content = tool.invoke(tool_args)
                except Exception as tool_err:
                    logger.exception("Tool '%s' failed: %s", tool_name, tool_err)
                    result_content = f"Error executing tool '{tool_name}': {tool_err}"

            messages.append(ToolMessage(content=str(result_content), tool_call_id=tool_call_id))

    def stream_reply(
        self,
        conversation: Conversation,
        on_token: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Stream *conversation*'s latest message to the LLM.

        Calls *on_token* for each streamed chunk, *on_done* with the
        full assembled reply, and *on_error* on failure.  Runs in a
        daemon thread; returns immediately.

        If the model requests tool calls, they are executed and their
        results are fed back to the model (as ``ToolMessage`` entries)
        so it can produce a final natural-language answer, repeating
        until the model stops requesting tools or ``_MAX_TOOL_ITERATIONS``
        is reached.
        """
        self._cancel_event.clear()

        def _stream_once(messages: List[BaseMessage]) -> tuple[list[str], Any]:
            """Stream a single LLM turn; returns (tokens, last_chunk)."""
            reply_tokens: list[str] = []
            last_chunk = None
            for chunk in llm.stream(messages):
                if self._cancel_event.is_set():
                    break
                last_chunk = chunk
                token: str = chunk.content  # type: ignore[assignment]
                if token:
                    reply_tokens.append(token)
                    on_token(token)
            return reply_tokens, last_chunk

        def _worker() -> None:
            try:
                nonlocal llm
                llm = self._get_llm()
                messages = _conv_to_messages(conversation)

                full_reply, last_chunk = _stream_once(messages)

                iterations = 0
                while (
                    not self._cancel_event.is_set()
                    and last_chunk is not None
                    and getattr(last_chunk, "tool_calls", None)
                    and iterations < _MAX_TOOL_ITERATIONS
                ):
                    iterations += 1
                    self._run_tool_calls(
                        tool_calls=last_chunk.tool_calls,
                        assistant_reply="".join(full_reply),
                        messages=messages,
                    )
                    # Ask the model again, now with the tool results in context.
                    full_reply, last_chunk = _stream_once(messages)

                if (
                    iterations >= _MAX_TOOL_ITERATIONS
                    and last_chunk is not None
                    and getattr(last_chunk, "tool_calls", None)
                ):
                    logger.warning(
                        "Reached max tool-calling iterations (%d); returning last partial reply.",
                        _MAX_TOOL_ITERATIONS,
                    )

                on_done("".join(full_reply))
            except Exception as exc:
                logger.exception("Agent error: %s", exc)
                on_error(_get_error_msg(exc))

        llm: BaseChatModel = None  # bound inside _worker via nonlocal
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def cancel(self) -> None:
        """Signal the running stream to stop."""
        self._cancel_event.set()

    def reset(self) -> None:
        """Clear cancellation state (call before a new conversation)."""
        self._cancel_event.clear()
        self._tools = []
        self._llm = None