"""
src/seneca/ui/chat_area.py – Scrollable container for chat bubbles.

:class:`ChatArea` owns the vertical scrolling region that holds
:class:`UserBubble` and :class:`AssistantBubble` widgets.  The
chat area occupies the top 85 % of the right-hand panel.
"""

from __future__ import annotations

import customtkinter as ctk
from seneca.ui.bubble import AssistantBubble, UserBubble

from config.settings import COLOR_BG


class ChatArea(ctk.CTkScrollableFrame):
    """
    Vertically scrollable frame that displays the conversation.

    Bubbles are added via :meth:`add_user_message` and
    :meth:`add_assistant_bubble`; the frame auto-scrolls to the
    bottom after each addition.
    """

    def __init__(self, parent: ctk.CTkFrame, **kwargs) -> None:
        super().__init__(
            parent,
            fg_color=COLOR_BG,
            scrollbar_button_color="#2e3650",
            scrollbar_button_hover_color="#4f8ef7",
            **kwargs,
        )

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

    def clear(self) -> None:
        """Remove all child widgets (new conversation)."""
        for widget in self.winfo_children():
            widget.destroy()

    def scroll_to_bottom(self) -> None:
        """Force the scrollable canvas to the very bottom."""
        self.after(10, lambda: self._parent_canvas.yview_moveto(1.0))
