"""
src/seneca/ui/bubble.py – Chat bubble widgets for the conversation area.

Two flavours:
- :class:`UserBubble`  – right-aligned, accent-coloured
- :class:`AssistantBubble` – left-aligned, surface-coloured with logo
"""

from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk
from PIL import Image

# Make sure the project root is on sys.path
_ROOT = Path(__file__).parent.parent.parent.parent

from config.settings import (
    COLOR_ACCENT,
    COLOR_AI_BUBBLE,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_USER_BUBBLE,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
)


class UserBubble(ctk.CTkFrame):
    """A right-aligned speech bubble for the user's messages."""

    def __init__(self, parent: ctk.CTkScrollableFrame, text: str) -> None:
        super().__init__(
            parent,
            fg_color="transparent",
        )
        self.grid_columnconfigure(0, weight=1)

        # Spacer pushes bubble to the right
        spacer = ctk.CTkFrame(self, fg_color="transparent", width=60)
        spacer.grid(row=0, column=0, sticky="ew")

        bubble = ctk.CTkFrame(
            self,
            fg_color=COLOR_USER_BUBBLE,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_ACCENT,
        )
        bubble.grid(row=0, column=1, padx=(0, 4), pady=(4, 0), sticky="e")

        label = ctk.CTkLabel(
            bubble,
            text=text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BODY),
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=440,
            justify="left",
            anchor="w",
        )
        label.pack(padx=16, pady=10)

        self.pack(fill="x", padx=12, pady=(8, 0))


class AssistantBubble(ctk.CTkFrame):
    """A left-aligned streaming bubble for Seneca's replies."""

    def __init__(self, parent: ctk.CTkScrollableFrame) -> None:
        super().__init__(
            parent,
            fg_color="transparent",
        )
        self.grid_columnconfigure(1, weight=1)

        # Load logo image as avatar
        logo_path = _ROOT / "assets" / "icons" / "logo-seneca-ai-blue-transparent.png"
        self._avatar_img = ctk.CTkImage(
            light_image=Image.open(logo_path),
            dark_image=Image.open(logo_path),
            size=(28, 28)
        )

        # Logo / avatar column
        avatar = ctk.CTkLabel(
            self,
            text="",
            image=self._avatar_img,
            width=32,
        )
        avatar.grid(row=0, column=0, padx=(4, 6), pady=(8, 0), sticky="n")

        self._bubble = ctk.CTkFrame(
            self,
            fg_color=COLOR_AI_BUBBLE,
            corner_radius=16,
            border_width=1,
            border_color=COLOR_BORDER,
        )
        self._bubble.grid(row=0, column=1, padx=(0, 60), pady=(4, 0), sticky="w")

        self._label = ctk.CTkLabel(
            self._bubble,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BODY),
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=440,
            justify="left",
            anchor="w",
        )
        self._label.pack(padx=16, pady=10)

        self._text_buffer: list[str] = []

        self.pack(fill="x", padx=12, pady=(8, 0))

    def append_token(self, token: str) -> None:
        """Append *token* to the bubble text (called from the main thread)."""
        self._text_buffer.append(token)
        self._label.configure(text="".join(self._text_buffer))

    def set_error(self, message: str) -> None:
        """Replace bubble content with an error message."""
        self._text_buffer = [message]
        self._label.configure(
            text=message,
            text_color="#e05c5c",
        )

    @property
    def full_text(self) -> str:
        """Return the complete assembled text."""
        return "".join(self._text_buffer)
