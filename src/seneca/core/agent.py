"""
src/seneca/core/agent.py – LangChain-backed AI agent for Seneca.

Supports multiple LLM providers (OpenAI, Ollama, Anthropic) chosen
via the ``LLM_PROVIDER`` environment variable.  The agent streams
its reply token-by-token, calling *on_token* for each chunk so the
UI can display text progressively.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Callable, List, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool

from seneca.core.conversation import Conversation, Role
from seneca.utils.config import config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Eres Seneca-AI, un asistente europeo de código abierto, "
    "diseñado para apoyar y empoderar a las personas, nunca para "
    "reemplazarlas. Responde siempre con claridad, respeto y rigor. "
    "Adapta el idioma al del usuario."
)


def _build_llm() -> BaseChatModel:
    """Instantiate the correct LLM based on *config.llm_provider*."""
    provider = config.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415
        return ChatOpenAI(
            model=config.openai_model,
            api_key=config.openai_api_key,
            streaming=True,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama  # noqa: PLC0415
        return ChatOllama(
            model=config.ollama_model,
            base_url=config.ollama_base_url,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
        return ChatAnthropic(
            model=config.anthropic_model,
            api_key=config.anthropic_api_key,
            streaming=True,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'")


def _conv_to_messages(
    conv: Conversation,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    """Convert a :class:`Conversation` into LangChain message objects."""
    msgs: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=_SYSTEM_PROMPT)
    ]
    role_map = {Role.USER: HumanMessage, Role.ASSISTANT: AIMessage}
    for m in conv.messages:
        msgs.append(role_map[m.role](content=m.content))
    return msgs


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
        """Robust check for tool-calling support in an LLM."""
        llm = None

        try:
            llm = self._get_llm()

            # --- 1. Explicit capability metadata (best case) ---
            profile = getattr(llm, "profile", None)
            if profile is not None:
                tool_flag = getattr(profile, "tool_calling", None)
                if isinstance(tool_flag, bool):
                    return tool_flag

            # --- 2. Interface-based detection ---
            bind_tools = getattr(llm, "bind_tools", None)
            if callable(bind_tools):
                return True

            # --- 3. Known provider-specific attributes ---
            # (extensible registry would be better)
            provider_flags = [
                "supports_tool_calling",
                "tool_calling",
                "function_calling",  # OpenAI-style naming
            ]

            for attr in provider_flags:
                val = getattr(llm, attr, None)
                if isinstance(val, bool):
                    return val

            # --- 4. Optional: lightweight behavioral probe ---
            if hasattr(llm, "invoke"):
                try:
                    test_tool = {
                        "name": "test_tool",
                        "description": "test",
                        "parameters": {"type": "object", "properties": {}},
                    }

                    # Try binding tools (non-invasive)
                    if callable(bind_tools):
                        llm_with_tools = bind_tools([test_tool])
                        return llm_with_tools is not None
                except Exception as probe_err:
                    logger.debug(f"Tool probe failed: {probe_err}")

            return False

        except Exception as e:
            logger.error(f"Error checking tool support: {e}")
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
        """
        self._cancel_event.clear()

        def _worker() -> None:
            full_reply: list[str] = []
            try:
                llm = self._get_llm()
                messages = _conv_to_messages(conversation)
                
                # To handle tool calls, we track the last message chunk
                last_chunk = None

                for chunk in llm.stream(messages):
                    if self._cancel_event.is_set():
                        break
                    
                    last_chunk = chunk
                    token: str = chunk.content  # type: ignore[assignment]
                    if token:
                        full_reply.append(token)
                        on_token(token)

                # Handle tool calls if any were generated
                if last_chunk and hasattr(last_chunk, "tool_calls") and last_chunk.tool_calls:
                    for tool_call in last_chunk.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        # Find and execute the corresponding tool
                        for tool in self._tools:
                            if tool.name == tool_name:
                                tool.invoke(tool_args)
                                break

                on_done("".join(full_reply))
            except Exception as exc:
                logger.exception("Agent error: %s", exc)
                on_error(_get_error_msg(exc))

        def _get_error_msg(exc: Exception) -> str:
            error_str = str(exc)
            final_error_msg = error_str

            # Attempt to parse the error as JSON to extract the 'message' field if present
            try:
                if hasattr(exc, "body") and isinstance(exc.body, dict) and "message" in exc.body:
                    final_error_msg = str(exc.body["message"])
            except (json.JSONDecodeError, TypeError):
                # Fallback to the default string representation of the exception
                pass
            return final_error_msg

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
