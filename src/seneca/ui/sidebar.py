"""
src/seneca/ui/sidebar.py – Collapsible left-hand navigation sidebar.

The sidebar is hidden by default and slides in/out when the hamburger
button is pressed.  It contains:
- "New conversation" action
- List of the 20 most recent conversation titles

Width is fixed (SIDEBAR_WIDTH); animation is achieved by repeatedly
adjusting the column weight via ``grid_columnconfigure``.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from config.settings import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_SIDEBAR,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    SIDEBAR_WIDTH,
)
from seneca.core.conversation import Conversation


class Sidebar(ctk.CTkFrame):
    """
    Sliding left-hand sidebar.

    Parameters
    ----------
    parent:
        Parent container that owns ``column 0``.
    on_new_conversation:
        Called with no arguments when the user requests a new chat.
    on_select_conversation:
        Called with the selected :class:`Conversation` object.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_new_conversation: Callable[[], None],
        on_select_conversation: Callable[[Conversation], None],
    ) -> None:
        super().__init__(
            parent,
            fg_color=COLOR_SIDEBAR,
            corner_radius=0,
            width=SIDEBAR_WIDTH,
            border_width=0,
        )
        self._on_new = on_new_conversation
        self._on_select = on_select_conversation
        self._visible = False
        self._conv_buttons: list[ctk.CTkButton] = []

        self._build()

    # ── Construction ──────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        # New conversation button
        new_btn = ctk.CTkButton(
            self,
            text="✏  Nueva conversación",
            font=ctk.CTkFont(
                family=FONT_FAMILY, size=FONT_SIZE_BODY, weight="bold"
            ),
            fg_color="transparent",
            hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
            corner_radius=8,
            command=self._on_new,
        )
        new_btn.grid(
            row=0, column=0, padx=12, pady=(20, 8), sticky="ew"
        )

        divider = ctk.CTkFrame(
            self, height=1, fg_color=COLOR_BORDER, corner_radius=0
        )
        divider.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

        heading = ctk.CTkLabel(
            self,
            text="CONVERSACIONES",
            font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        heading.grid(row=2, column=0, padx=16, pady=(4, 6), sticky="w")

        # Scrollable list for conversation history
        self._list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT,
        )
        self._list_frame.grid(
            row=3, column=0, padx=4, pady=0, sticky="nsew"
        )
        self.grid_rowconfigure(3, weight=1)

    # ── Public API ────────────────────────────────────────────────────────

    def toggle(self) -> None:
        """Show or hide the sidebar."""
        self._visible = not self._visible
        if self._visible:
            self.grid(row=0, column=0, sticky="nsew")
        else:
            self.grid_remove()

    @property
    def is_visible(self) -> bool:
        """Return *True* if the sidebar is currently shown."""
        return self._visible

    def populate(self, conversations: list[Conversation]) -> None:
        """
        Re-render the conversation list.

        Clears any previous buttons and creates one per conversation.
        """
        for btn in self._conv_buttons:
            btn.destroy()
        self._conv_buttons.clear()

        for conv in conversations:
            title = conv.derive_title() or conv.title
            btn = ctk.CTkButton(
                self._list_frame,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_SMALL),
                fg_color="transparent",
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w",
                corner_radius=6,
                command=lambda c=conv: self._on_select(c),
            )
            btn.pack(fill="x", padx=4, pady=2)
            self._conv_buttons.append(btn)
