"""
src/seneca/ui/chat_area.py – Scrollable container for chat bubbles.

:class:`ChatArea` owns the vertical scrolling region that holds
:class:`UserBubble` and :class:`AssistantBubble` widgets.  The
chat area occupies the top 85 % of the right-hand panel.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from PIL import Image

from config.settings import (
    COLOR_BG,
    COLOR_TEXT_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_BODY,
)
from seneca.i18n.locale import I18n
from seneca.ui.bubble import AssistantBubble, UserBubble

_ROOT = Path(__file__).parent.parent.parent.parent


class ChatArea(ctk.CTkScrollableFrame):
    """
    Vertically scrollable frame that displays the conversation.

    Bubbles are added via :meth:`add_user_message` and
    :meth:`add_assistant_bubble`; the frame auto-scrolls to the
    bottom after each addition.
    """

    def __init__(self, parent: ctk.CTkFrame, i18n: I18n, **kwargs) -> None:
        super().__init__(
            parent,
            fg_color=COLOR_BG,
            scrollbar_button_color="#2e3650",
            scrollbar_button_hover_color="#4f8ef7",
            **kwargs,
        )
        self._i18n = i18n

        # Load logo image for thinking message
        logo_path = _ROOT / "assets" / "icons" / "logo-seneca-ai-blue-transparent.png"
        self._avatar_img = ctk.CTkImage(
            light_image=Image.open(logo_path),
            dark_image=Image.open(logo_path),
            size=(28, 28)
        )

        # Thinking message frame (initially hidden)
        self._thinking_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._thinking_frame.grid_columnconfigure(1, weight=1) # Allow label to expand

        avatar = ctk.CTkLabel(
            self._thinking_frame,
            text="",
            image=self._avatar_img,
            width=32,
        )
        avatar.grid(row=0, column=0, padx=(4, 6), pady=(8, 0), sticky="n")

        self._thinking_label = ctk.CTkLabel(
            self._thinking_frame,
            text=self._i18n.t("thinking_message"),
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color="transparent",
            anchor="w",
            justify="left",
        )
        self._thinking_label.grid(row=0, column=1, padx=(0, 60), pady=(8, 0), sticky="w")
        
        self._thinking_frame.pack_forget() # Hide initially


    def add_user_message(self, text: str) -> None:
        """Render *text* in a :class:`UserBubble` and scroll down."""
        UserBubble(self, text)
        self.scroll_to_bottom()

    def add_assistant_bubble(self) -> AssistantBubble:
        """
        Add an empty :class:`AssistantBubble` ready for token streaming.

        Returns the bubble so the caller can call
        :meth:`~AssistantBubble.append_token` on it.
        """
        bubble = AssistantBubble(self)
        self.scroll_to_bottom()
        return bubble

    def show_thinking_message(self) -> None:
        """Display the 'Thinking...' message."""
        self._thinking_frame.pack(fill="x", padx=12, pady=(8, 0))
        self.scroll_to_bottom()

    def hide_thinking_message(self) -> None:
        """Hide the 'Thinking...' message."""
        self._thinking_frame.pack_forget()

    def clear(self) -> None:
        """Remove all child widgets (new conversation)."""
        for widget in self.winfo_children():
            # Don't destroy the thinking frame, just hide it
            if widget is not self._thinking_frame:
                widget.destroy()
        self.hide_thinking_message() # Ensure it's hidden on clear

    def scroll_to_bottom(self) -> None:
        """Force the scrollable canvas to the very bottom."""
        self.after(10, lambda: self._parent_canvas.yview_moveto(1.0))
