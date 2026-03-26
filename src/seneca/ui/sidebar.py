"""
src/seneca/ui/sidebar.py – Collapsible left-hand navigation sidebar.

The sidebar is always visible in a collapsed state (showing only the
hamburger icon) and can be expanded to show full menu options.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from PIL import Image

# Make sure the project root is on sys.path
_ROOT = Path(__file__).parent.parent.parent.parent

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
    SIDEBAR_COLLAPSED_WIDTH,
)
from seneca.core.conversation import Conversation
from seneca.i18n.locale import I18n


class Sidebar(ctk.CTkFrame):
    """
    Collapsible left-hand sidebar.

    Parameters
    ----------
    parent:
        Parent container that owns ``column 0``.
    on_toggle:
        Called when the hamburger button is clicked.
    on_new_conversation:
        Called with no arguments when the user requests a new chat.
    on_select_conversation:
        Called with the selected :class:`Conversation` object.
    i18n:
        Internationalisation helper.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_toggle: Callable[[], None],
        on_new_conversation: Callable[[], None],
        on_select_conversation: Callable[[Conversation], None],
        i18n: I18n,
    ) -> None:
        super().__init__(
            parent,
            fg_color=COLOR_SIDEBAR,
            corner_radius=0,
            width=SIDEBAR_COLLAPSED_WIDTH,
            border_width=0,
        )
        self._on_toggle = on_toggle
        self._on_new = on_new_conversation
        self._on_select = on_select_conversation
        self._i18n = i18n
        self._expanded = False
        self._conv_buttons: list[ctk.CTkButton] = []

        self._load_icons()
        self._build()

    def _load_icons(self) -> None:
        """Load icon images for the buttons."""
        icons_dir = _ROOT / "assets" / "icons"
        self._icon_pencil = ctk.CTkImage(
            light_image=Image.open(icons_dir / "pencil-black.png"),
            dark_image=Image.open(icons_dir / "pencil-white.png"),
            size=(20, 20)
        )

    # ── Construction ──────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        # Hamburger button (Always visible)
        self._ham_btn = ctk.CTkButton(
            self,
            text="☰",
            width=40,
            height=40,
            corner_radius=8,
            fg_color="transparent",
            hover_color=COLOR_BORDER,
            font=ctk.CTkFont(size=20),
            text_color=COLOR_TEXT_PRIMARY,
            command=self._on_toggle,
        )
        self._ham_btn.grid(row=0, column=0, padx=10, pady=(4, 10), sticky="nw")

        # Container for elements that are hidden when collapsed
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        # Do not grid content_frame yet as we start collapsed

        # New conversation button
        self._new_btn = ctk.CTkButton(
            self._content_frame,
            text=f" {self._i18n.t('new_conversation')}",
            image=self._icon_pencil,
            compound="left",
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
        self._new_btn.grid(
            row=0, column=0, padx=12, pady=(10, 8), sticky="ew"
        )

        self._divider = ctk.CTkFrame(
            self._content_frame, height=1, fg_color=COLOR_BORDER, corner_radius=0
        )
        self._divider.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

        self._heading = ctk.CTkLabel(
            self._content_frame,
            text=self._i18n.t("conversations").upper(),
            font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        self._heading.grid(row=2, column=0, padx=16, pady=(4, 6), sticky="w")

        # Scrollable list for conversation history
        self._list_frame = ctk.CTkScrollableFrame(
            self._content_frame,
            fg_color="transparent",
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_ACCENT,
        )
        self._list_frame.grid(
            row=3, column=0, padx=4, pady=0, sticky="nsew"
        )
        self._content_frame.grid_rowconfigure(3, weight=1)
        self._content_frame.grid_columnconfigure(0, weight=1)

    # ── Public API ────────────────────────────────────────────────────────

    def set_expanded(self, expanded: bool) -> None:
        """Update the UI based on expansion state."""
        self._expanded = expanded
        if expanded:
            self.configure(width=SIDEBAR_WIDTH)
            self._content_frame.grid(row=1, column=0, sticky="nsew")
            self.grid_rowconfigure(1, weight=1)
        else:
            self.configure(width=SIDEBAR_COLLAPSED_WIDTH)
            self._content_frame.grid_remove()
            self.grid_rowconfigure(1, weight=0)

    @property
    def is_expanded(self) -> bool:
        """Return *True* if the sidebar is currently expanded."""
        return self._expanded

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
