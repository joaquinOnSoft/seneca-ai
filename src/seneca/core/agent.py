"""
src/seneca/core/agent.py – Chat agent of the desktop app.

The LLM runs on the Seneca-AI API server (``POST /senecaai/v1/chat``):
the agent sends the user's message, receives the reply as a stream of
Server-Sent Events and forwards each chunk to the UI through *on_token*.
The server builds the prompt from the stored conversation, selects the
provider (``LLM_PROVIDER`` in the api container) and stores both messages.

Tools (e.g. "open the reply in Notepad") act on the user's computer, so
they still run here: the agent sends their JSON-schema definitions with
the message; when the model calls one, the server sends a ``tool_calls``
event, the agent runs the tools and sends the results back, and the server
resumes the reply.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import requests
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from seneca.api.client import ChatStream, SenecaApiClient, SenecaApiError
from seneca.core.api_storage import create_api_client
from seneca.core.conversation import Conversation, Role

logger = logging.getLogger(__name__)

# Seconds before asking the API for its capabilities again after a failure
_CAPABILITIES_RETRY_SECONDS = 30.0


def _as_tool(tool_func: Callable) -> BaseTool:
    """Wrap a plain function as a LangChain tool (to get its JSON schema)."""
    if isinstance(tool_func, BaseTool):
        return tool_func
    return StructuredTool.from_function(
        func=tool_func,
        name=tool_func.__name__,
        description=tool_func.__doc__ or f"Execute {tool_func.__name__}",
    )


def _tool_name(tool_func: Callable) -> str:
    return getattr(tool_func, "name", None) or tool_func.__name__


def _error_message(exc: Exception) -> str:
    if isinstance(exc, SenecaApiError):
        return str(exc)
    if isinstance(exc, requests.ConnectionError):
        return "Cannot connect to the Seneca AI API server."
    if isinstance(exc, requests.Timeout):
        return "The Seneca AI API server did not answer in time."
    return str(exc) or exc.__class__.__name__


class SenecaAgent:
    """Streams replies from the Seneca-AI API and runs the client-side tools.

    :meth:`stream_reply` runs in a daemon thread and delivers each chunk
    via a callback, so the UI stays responsive.
    """

    def __init__(self, client: Optional[SenecaApiClient] = None) -> None:
        self._client = client or create_api_client(max_retries=1)
        self._cancel_event = threading.Event()
        self._tools: Dict[str, BaseTool] = {}
        self._tool_calling: Optional[bool] = None
        self._capabilities_retry_at = 0.0
        # Stream being read, so cancel() can close it from the UI thread
        self._stream: Optional[ChatStream] = None
        self._stream_lock = threading.Lock()

    # -- tools -----------------------------------------------------------------

    def supports_tools(self) -> bool:
        """Whether the server's model supports tool calling (asked once to the API)."""
        if self._tool_calling is None:
            # The UI calls this on the main thread: after a failure, wait a
            # while before asking again instead of blocking it on every call
            if time.monotonic() < self._capabilities_retry_at:
                return False
            try:
                self._tool_calling = self._client.get_chat_capabilities().tool_calling
            except (SenecaApiError, requests.RequestException) as exc:
                logger.warning("Could not get the chat capabilities from the API: %s", exc)
                self._capabilities_retry_at = time.monotonic() + _CAPABILITIES_RETRY_SECONDS
                return False
        return self._tool_calling

    def add_tool(self, tool_func: Callable) -> None:
        """Offer *tool_func* to the model in the next replies."""
        if not self.supports_tools():
            logger.warning("Attempted to add a tool, but the server's model doesn't support tool calling.")
            return
        name = _tool_name(tool_func)
        if name not in self._tools:
            self._tools[name] = _as_tool(tool_func)

    def remove_tool(self, tool_func: Callable) -> None:
        """Stop offering *tool_func* to the model."""
        self._tools.pop(_tool_name(tool_func), None)

    def _tool_specs(self) -> List[Dict[str, Any]]:
        """Definitions sent to the server: ``{"name", "description", "parameters"}``."""
        return [convert_to_openai_tool(tool)["function"] for tool in self._tools.values()]

    def _run_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Run the tools requested by the model and return their results."""
        results = []
        for call in tool_calls:
            name, args = call.get("name", ""), call.get("args") or {}
            tool = self._tools.get(name)
            if tool is None:
                logger.warning("Model requested unknown tool '%s'.", name)
                content = f"Error: tool '{name}' not found."
            else:
                try:
                    content = str(tool.invoke(args))
                except Exception as exc:  # noqa: BLE001 – the error is reported to the model
                    logger.exception("Tool '%s' failed: %s", name, exc)
                    content = f"Error executing tool '{name}': {exc}"
            results.append({"tool_call_id": call["id"], "content": content})
        return results

    # -- streaming -------------------------------------------------------------

    def _open_stream(self, **kwargs: Any) -> Optional[ChatStream]:
        """Open a chat stream, unless the user has already cancelled."""
        stream = self._client.stream_chat(**kwargs)
        with self._stream_lock:
            if self._cancel_event.is_set():
                stream.close()
                return None
            self._stream = stream
        return stream

    def stream_reply(
        self,
        conversation: Conversation,
        on_token: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Send *conversation*'s latest user message and stream the reply.

        Calls *on_token* for each streamed chunk and then either *on_done*
        with the full reply (also after a cancellation, with the partial
        reply, which the server has stored too) or *on_error*.  Runs in a
        daemon thread; returns immediately.

        When the server creates the conversation, ``conversation.id``,
        ``conversation.title`` and ``conversation.stored`` are updated.
        """
        self._cancel_event.clear()
        content = next(
            (m.content for m in reversed(conversation.messages) if m.role == Role.USER), ""
        )

        def _worker() -> None:
            reply: List[str] = []
            try:
                stream = self._open_stream(
                    content=content,
                    conversation_id=conversation.id if conversation.stored else None,
                    tools=self._tool_specs(),
                )
                while stream is not None:
                    next_stream = None
                    for event in stream:
                        if event.event == "conversation":
                            conversation.id = event.data["id"]
                            conversation.title = event.data.get("title") or conversation.title
                            conversation.stored = True
                        elif event.event == "token":
                            reply.append(event.data["text"])
                            on_token(event.data["text"])
                        elif event.event == "tool_calls":
                            results = self._run_tool_calls(event.data["tool_calls"])
                            if not self._cancel_event.is_set():
                                next_stream = self._open_stream(
                                    conversation_id=conversation.id,
                                    tool_results=results,
                                    tools=self._tool_specs(),
                                )
                            break
                        elif event.event == "error":
                            on_error(event.data.get("error", "Unknown error"))
                            return
                        elif event.event == "done":
                            break
                    stream.close()
                    stream = next_stream
                on_done("".join(reply))
            except Exception as exc:  # noqa: BLE001 – reported to the UI
                if self._cancel_event.is_set():
                    on_done("".join(reply))
                    return
                logger.exception("Chat error: %s", exc)
                on_error(_error_message(exc))
            finally:
                with self._stream_lock:
                    self._stream = None

        threading.Thread(target=_worker, daemon=True).start()

    def cancel(self) -> None:
        """Stop the running reply: closing the stream makes the server stop the LLM."""
        with self._stream_lock:
            self._cancel_event.set()
            if self._stream is not None:
                self._stream.close()

    def reset(self) -> None:
        """Clear cancellation state and tools (call before a new conversation)."""
        self._cancel_event.clear()
        self._tools = {}
