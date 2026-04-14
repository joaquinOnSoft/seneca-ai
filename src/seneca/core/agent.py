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
from typing import Callable, Generator

import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

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
        from langchain_community.chat_models import ChatOllama  # noqa: PLC0415
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

    def _get_llm(self) -> BaseChatModel:
        if self._llm is None:
            self._llm = _build_llm()
        return self._llm

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
                for chunk in llm.stream(messages):
                    if self._cancel_event.is_set():
                        break
                    token: str = chunk.content  # type: ignore[assignment]
                    full_reply.append(token)
                    on_token(token)
                on_done("".join(full_reply))
            except Exception as exc:
                logger.exception("Agent error: %s", exc)
                error_str = str(exc)
                final_error_msg = error_str

                # We try to parse the erros as JSON to extract the 'message'
                try:
                    if hasattr(exc, "body") and isinstance(exc.body, dict) and "message" in exc.body:
                        final_error_msg = str(exc.body["message"])
                except (json.JSONDecodeError, TypeError):
                    # Si no es un JSON válido o hay error en el proceso,
                    # mantenemos el comportamiento actual (error_str)
                    pass

                on_error(final_error_msg)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def cancel(self) -> None:
        """Signal the running stream to stop."""
        self._cancel_event.set()

    def reset(self) -> None:
        """Clear cancellation state (call before a new conversation)."""
        self._cancel_event.clear()
