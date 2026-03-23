"""
src/seneca/ui/main_window.py – Root application window for Seneca-AI.

Wires together the sidebar, chat area, input bar, and AI agent into a
single cohesive UI.  All cross-component communication goes through
this class so individual widgets remain decoupled.

Layout (grid)
─────────────
col 0 (0 px / SIDEBAR_WIDTH)  │  col 1 (1*)
─────────────────────────────────────────────
 [Sidebar – hidden by default] │  [Title bar + hamburger]
                                │  [Chat area        85%]
                                │  [Input bar        15%]
"""

from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

# Make sure the project root is on sys.path when running from src/
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import (
    APP_TITLE,
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_SIDEBAR,
    COLOR_SURFACE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_SIZE_TITLE,
    INPUT_HEIGHT_RATIO,
    INPUT_MARGIN_BOTTOM,
    INPUT_MARGIN_RIGHT,
    SIDEBAR_WIDTH,
    THEME,
    COLOR_THEME,
)
from seneca.core.agent import SenecaAgent
from seneca.core.conversation import Conversation, Role
from seneca.core import storage
from seneca.i18n.locale import I18n
from seneca.ui.chat_area import ChatArea
from seneca.ui.input_bar import InputBar
from seneca.ui.sidebar import Sidebar
from seneca.utils.config import config


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
        self._history: list[Conversation] = storage.load_conversations(
            config.max_conversations
        )
        self._current_bubble = None  # AssistantBubble | None

        self._setup_window()
        self._build_ui()
        self._refresh_sidebar_history()

    # ── Window setup ──────────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.title(APP_TITLE)
        self.geometry("900x680")
        self.minsize(640, 480)
        self.configure(fg_color=COLOR_BG)

        # Two-column grid: sidebar (hidden) | main content
        self.grid_columnconfigure(0, weight=0, minsize=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_sidebar()
        self._build_main_panel()

    def _build_sidebar(self) -> None:
        self._sidebar = Sidebar(
            parent=self,
            on_new_conversation=self._on_new_conversation,
            on_select_conversation=self._on_load_conversation,
        )
        # sidebar starts hidden – do not grid it yet

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

        # Hamburger button
        ham_btn = ctk.CTkButton(
            bar,
            text="☰",
            width=40,
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLOR_BORDER,
            font=ctk.CTkFont(size=20),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._toggle_sidebar,
        )
        ham_btn.grid(row=0, column=0, padx=(10, 4), pady=4)

        # App title
        title_lbl = ctk.CTkLabel(
            bar,
            text=APP_TITLE,
            font=ctk.CTkFont(
                family=FONT_FAMILY, size=FONT_SIZE_TITLE, weight="bold"
            ),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        )
        title_lbl.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        # Thin separator
        sep = ctk.CTkFrame(
            self._main, height=1, fg_color=COLOR_BORDER, corner_radius=0
        )
        sep.grid(row=0, column=0, sticky="sew")

    def _build_chat_area(self) -> None:
        self._chat = ChatArea(self._main)
        self._chat.grid(
            row=1, column=0, sticky="nsew", padx=0, pady=0
        )

    def _build_input_bar(self) -> None:
        self._input = InputBar(
            parent=self._main,
            on_submit=self._on_submit,
            on_cancel=self._on_cancel,
            placeholder=self._i18n.t("placeholder"),
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
        if self._sidebar.is_visible:
            self._sidebar.grid_remove()
            self._sidebar._visible = False
            self.grid_columnconfigure(0, weight=0, minsize=0)
        else:
            self._sidebar.grid(row=0, column=0, sticky="nsew")
            self._sidebar._visible = True
            self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)

    def _on_new_conversation(self) -> None:
        """Reset the UI and create a blank conversation."""
        self._agent.cancel()
        self._agent.reset()
        self._active_conversation = Conversation()
        self._chat.clear()
        self._input.set_thinking(False)
        self._current_bubble = None

    def _on_load_conversation(self, conv: Conversation) -> None:
        """Replay a historical conversation in the chat area."""
        self._agent.cancel()
        self._agent.reset()
        self._active_conversation = conv
        self._chat.clear()
        for msg in conv.messages:
            if msg.role == Role.USER:
                self._chat.add_user_message(msg.content)
            else:
                bubble = self._chat.add_assistant_bubble()
                bubble.append_token(msg.content)
        self._input.set_thinking(False)
        self._current_bubble = None

    def _on_submit(self, text: str) -> None:
        """Handle a new user prompt."""
        # Add user message to data model and UI
        self._active_conversation.add_message(Role.USER, text)
        self._chat.add_user_message(text)

        # Prepare streaming bubble
        self._current_bubble = self._chat.add_assistant_bubble()
        self._input.set_thinking(True)

        # Stream agent reply
        self._agent.stream_reply(
            conversation=self._active_conversation,
            on_token=self._on_token,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_cancel(self) -> None:
        """User clicked the stop button."""
        self._agent.cancel()
        self._input.set_thinking(False)

    def _on_token(self, token: str) -> None:
        """Deliver a streamed token to the UI (called from worker thread)."""
        if self._current_bubble is not None:
            self.after(0, lambda t=token: self._current_bubble.append_token(t))

    def _on_done(self, full_reply: str) -> None:
        """Finalise a completed reply."""
        self._active_conversation.add_message(Role.ASSISTANT, full_reply)
        storage.save_conversation(self._active_conversation)

        # Update history list
        if self._active_conversation not in self._history:
            self._history.insert(0, self._active_conversation)
            self._history = self._history[: config.max_conversations]

        self.after(0, self._finish_thinking)

    def _on_error(self, message: str) -> None:
        """Display an error in the current bubble."""
        if self._current_bubble is not None:
            self.after(
                0,
                lambda m=message: self._current_bubble.set_error(
                    f"{self._i18n.t('error_prefix')}: {m}"
                ),
            )
        self.after(0, self._finish_thinking)

    def _finish_thinking(self) -> None:
        self._input.set_thinking(False)
        self._refresh_sidebar_history()

    def _refresh_sidebar_history(self) -> None:
        self._sidebar.populate(self._history)
