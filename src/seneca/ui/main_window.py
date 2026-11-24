"""
src/seneca/ui/main_window.py – Root application window for Seneca-AI.

Wires together the sidebar, chat area, input bar, and AI agent into a
single cohesive UI.  All cross-component communication goes through
this class so individual widgets remain decoupled.

Layout (grid)
─────────────
col 0 (SIDEBAR_COLLAPSED_WIDTH / SIDEBAR_WIDTH) │  col 1 (1*)
─────────────────────────────────────────────
 [Sidebar – persistent]                          │  [Title bar]
                                                 │  [Chat area        85%]
                                                 │  [Input bar        15%]
"""

from __future__ import annotations

import sys
from pathlib import Path
from tkinter import PhotoImage
from typing import Callable

import customtkinter as ctk

# Make sure the project root is on sys.path when running from src/
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import (
    COLOR_BG,
    COLOR_BORDER,
    COLOR_SURFACE,
    COLOR_TEXT_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_TITLE,
    INPUT_MARGIN_BOTTOM,
    INPUT_MARGIN_RIGHT,
    SIDEBAR_WIDTH,
    SIDEBAR_COLLAPSED_WIDTH,
    THEME,
    COLOR_THEME,
)
from seneca.core.agent import SenecaAgent
from seneca.core.conversation import Conversation, Role
from seneca.core.api_storage import ApiConversationStore
from seneca.i18n.locale import I18n
from seneca.ui.chat_area import ChatArea
from seneca.ui.input_bar import InputBar
from seneca.ui.sidebar import Sidebar
from seneca.utils.config import config
from seneca.core.stt_service import SpeechToTextService # Import the STT service

# Sentinel value to indicate a bubble is pending creation on the main thread
_BUBBLE_PENDING = object()


class MainWindow(ctk.CTk):
    """
    The root Tk window for Seneca-AI.

    Responsibilities
    ----------------
    - Build and lay out all child widgets.
    - Manage the active :class:`Conversation` and history.
    - Coordinate the :class:`SenecaAgent` streaming lifecycle.
    - Route inter-widget events (sidebar toggle, new chat, history load).
    """

    def __init__(self) -> None:
        ctk.set_appearance_mode(THEME)
        ctk.set_default_color_theme(COLOR_THEME)
        super().__init__()

        self._i18n = I18n(config.app_locale)
        self._agent = SenecaAgent()
        self._active_conversation: Conversation = Conversation()
        self._store = ApiConversationStore.from_config()
        self._history: list[Conversation] = self._store.load_conversations(
            config.max_conversations
        )
        self._current_bubble: ChatArea.AssistantBubble | None | object = None  # AssistantBubble | None | _BUBBLE_PENDING
        # Incremented whenever a reply starts or the chat is switched, so the
        # callbacks of an older (cancelled) reply no longer touch the UI
        self._turn = 0
        
        # Initialize SpeechToTextService
        self._stt_service = SpeechToTextService(
            on_transcription_complete=self._on_transcription_complete,
            on_error=self._on_stt_error
        )

        self._setup_window()
        self._build_ui()
        # Defer the call to _refresh_sidebar_history to ensure UI is fully built
        self.after(100, self._refresh_sidebar_history) # Call after 100ms

    # ── Speech-to-Text Callbacks ──────────────────────────────────────────

    def _on_transcription_complete(self, text: str) -> None:
        """Callback for when STT service completes transcription."""
        self.after(0, lambda: self._input.set_text(text))
        self.after(0, lambda: self._input.set_mic_recording(False)) # Reset mic button state

    def _on_stt_error(self, message: str) -> None:
        """Callback for when STT service encounters an error."""
        self.after(0, lambda: print(f"STT Error: {message}")) # For now, just print to console
        self.after(0, lambda: self._input.set_mic_recording(False)) # Reset mic button state

    def _on_mic_toggle(self) -> None:
        """Handles the mic button toggle event."""
        if self._stt_service.is_recording():
            self._stt_service.stop_recording()
            self._input.set_mic_recording(False)
        else:
            self._stt_service.start_recording()
            self._input.set_mic_recording(True)

    def _refresh_sidebar_history(self) -> None:
        """
        Actualiza la interfaz de la barra lateral con la lista de conversaciones cargadas.
        """
        self._sidebar.update_history(self._history, self._active_conversation.id)

    # ── Window setup ──────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.title(self._i18n.t("app_title"))
        logo = PhotoImage(file=_ROOT / "assets" / "icons" / "logo-seneca-ai-transparent.png")
        self.iconphoto(False, logo)
        self.geometry("900x680")
        self.minsize(640, 480)
        self.configure(fg_color=COLOR_BG)

        # Two-column grid: sidebar (fixed width) | main content (stretchy)
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_COLLAPSED_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_sidebar()
        self._build_main_panel()
        # Assign mic callbacks after input bar is fully built
        self._input.set_on_mic_toggle(self._on_mic_toggle)
        self._input.set_is_mic_recording_func(self._stt_service.is_recording)

    def _build_sidebar(self) -> None:
        self._sidebar = Sidebar(
            parent=self,
            on_toggle=self._toggle_sidebar,
            on_new_conversation=self._on_new_conversation,
            on_select_conversation=self._on_load_conversation,
            i18n=self._i18n,
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

    def _build_main_panel(self) -> None:
        """Right-hand panel: title bar + chat area + input bar."""
        self._main = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(1, weight=1)  # chat area grows

        self._build_title_bar()
        self._build_chat_area()
        self._build_input_bar()

    def _build_title_bar(self) -> None:
        bar = ctk.CTkFrame(
            self._main,
            height=48,
            fg_color=COLOR_SURFACE,
            corner_radius=0,
        )
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_propagate(False)

        # Empty label to maintain space (Note: Title removed as requested)
        title_lbl = ctk.CTkLabel(
            bar,
            text="",
            font=ctk.CTkFont(
                family=FONT_FAMILY, size=FONT_SIZE_TITLE, weight="bold"
            ),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, padx=16, pady=4, sticky="w")

        # Thin separator
        sep = ctk.CTkFrame(
            self._main, height=1, fg_color=COLOR_BORDER, corner_radius=0
        )
        sep.grid(row=0, column=0, sticky="sew")

    def _build_chat_area(self) -> None:
        self._chat = ChatArea(self._main, i18n=self._i18n)
        self._chat.grid(
            row=1, column=0, sticky="nsew", padx=0, pady=(0, 12)
        )

    def _build_input_bar(self) -> None:
        self._input = InputBar(
            parent=self._main,
            on_submit=self._on_submit,
            on_cancel=self._on_cancel,
            on_tool_added=self._on_tool_added,
            on_tool_removed=self._on_tool_removed,
            can_add_tools_func=self._agent.supports_tools,
            placeholder=self._i18n.t("placeholder"),
            # on_mic_toggle and is_mic_recording_func will be set after build_input_bar
        )
        self._input.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=(12, INPUT_MARGIN_RIGHT),
            pady=(6, INPUT_MARGIN_BOTTOM),
            ipady=6,
        )
        self._main.grid_rowconfigure(2, minsize=80)

    # ── Event handlers ────────────────────────────────────────────────────

    def _toggle_sidebar(self) -> None:
        if self._sidebar.is_expanded:
            self._sidebar.set_expanded(False)
            self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_COLLAPSED_WIDTH)
        else:
            self._sidebar.set_expanded(True)
            self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)

    def _on_new_conversation(self) -> None:
        """Reset the UI and create a blank conversation."""
        self._turn += 1
        self._agent.cancel()
        self._agent.reset()
        self._active_conversation = Conversation()
        self._chat.clear()
        self._chat.hide_thinking_message() # Ensure thinking message is hidden
        self._input.set_thinking(False)
        self._input.clear_tools()
        self._current_bubble = None
        self._refresh_sidebar_history() # Refresh sidebar to reflect new active conversation

    def _on_load_conversation(self, conv: Conversation) -> None:
        """Replay a historical conversation in the chat area."""
        self._turn += 1
        self._agent.cancel()
        self._agent.reset()
        self._store.ensure_messages(conv)  # history items may only hold a summary
        self._active_conversation = conv
        self._chat.clear()
        self._chat.hide_thinking_message() # Ensure thinking message is hidden
        for msg in conv.messages:
            if msg.role == Role.USER:
                self._chat.add_user_message(msg.content)
            else:
                bubble = self._chat.add_assistant_bubble()
                bubble.append_token(msg.content)
        
        # Asegurar que el scroll llegue al final tras cargar el historial
        self.update()
        self._chat.scroll_to_bottom()
        self._input.set_thinking(False)
        self._input.clear_tools()
        self._current_bubble = None
        self._refresh_sidebar_history() # Refresh sidebar to highlight active conversation

    def _on_submit(self, text: str) -> None:
        """Handle a new user prompt."""
        # Add user message to data model and UI
        self._active_conversation.add_message(Role.USER, text)
        self._chat.add_user_message(text)
        self.update()
        self._chat.scroll_to_bottom()

        # Show thinking message
        self._chat.show_thinking_message()
        self._input.set_thinking(True)
        self._current_bubble = _BUBBLE_PENDING # Indicate bubble creation is pending

        # Stream the reply; the API server calls the LLM and stores both messages
        self._turn += 1
        turn, conv = self._turn, self._active_conversation
        self._agent.stream_reply(
            conversation=conv,
            on_token=lambda token: self._on_token(turn, token),
            on_done=lambda reply: self._on_done(turn, conv, reply),
            on_error=lambda message: self._on_error(turn, message),
        )

    def _on_cancel(self) -> None:
        """User clicked the stop button."""
        self._agent.cancel()
        self._chat.hide_thinking_message() # Hide thinking message on cancel
        self._input.set_thinking(False)
        self._current_bubble = None # Reset current bubble on cancel

    def _on_tool_added(self, tool_func: Callable) -> None:
        """Called when a tool is selected from the input bar."""
        self._agent.add_tool(tool_func)

    def _on_tool_removed(self, tool_func: Callable) -> None:
        """Called when a tool is removed from the input bar."""
        self._agent.remove_tool(tool_func)

    def _on_token(self, turn: int, token: str) -> None:
        """Deliver a streamed token to the UI (called from worker thread)."""
        # Delegate all logic to the main thread to prevent multiple bubble creation
        self.after(0, self._process_token_main_thread, turn, token)

    def _process_token_main_thread(self, turn: int, token: str) -> None:
        """Handles bubble creation and token appending sequentially on the main thread."""
        if turn != self._turn:
            return  # token of a reply the user has left
        if self._current_bubble is _BUBBLE_PENDING:
            self._chat.hide_thinking_message()
            self._current_bubble = self._chat.add_assistant_bubble()
        
        if self._current_bubble is not None and self._current_bubble is not _BUBBLE_PENDING:
            self._current_bubble.append_token(token)
            # Forzar actualización de geometría y hacer scroll al final
            self.update()
            self._chat.scroll_to_bottom()

    def _on_done(self, turn: int, conv: Conversation, full_reply: str) -> None:
        """Finalise a completed (or cancelled) reply; the server has already stored it."""
        self.after(0, self._finish_reply_main_thread, turn, conv, full_reply)

    def _finish_reply_main_thread(self, turn: int, conv: Conversation, full_reply: str) -> None:
        # A cancelled reply keeps the text already shown, as the server does
        if full_reply:
            conv.add_message(Role.ASSISTANT, full_reply)

        # Update history list (the server created the conversation with the first message)
        if conv.stored and conv not in self._history:
            self._history.insert(0, conv)
            self._history = self._history[: config.max_conversations]

        if turn == self._turn:
            self._finish_thinking()
        else:
            self._refresh_sidebar_history()

    def _on_error(self, turn: int, message: str) -> None:
        """Display an error in the current bubble."""
        self.after(0, self._handle_error_main_thread, turn, message)

    def _handle_error_main_thread(self, turn: int, message: str) -> None:
        """Handles error display sequentially on the main thread."""
        if turn != self._turn:
            return  # error of a reply the user has left
        self._chat.hide_thinking_message()
        
        if self._current_bubble is _BUBBLE_PENDING:
            self._current_bubble = self._chat.add_assistant_bubble()
            
        if self._current_bubble is not None and self._current_bubble is not _BUBBLE_PENDING:
            error_text = f"{self._i18n.t('error_prefix')}: {message}"
            self._current_bubble.set_error(error_text)
            self.update()
            self._chat.scroll_to_bottom()
            
        self._finish_thinking()

    def _finish_thinking(self) -> None:
        self._chat.hide_thinking_message() # Ensure thinking message is hidden
        self._input.set_thinking(False)
        self._refresh_sidebar_history()
        self._current_bubble = None # Reset for next interaction