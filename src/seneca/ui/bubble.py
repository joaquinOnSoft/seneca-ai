"""
src/seneca/ui/bubble.py – Chat bubble widgets for the conversation area.

Two flavours:
- :class:`UserBubble`  – right-aligned, accent-coloured
- :class:`AssistantBubble` – left-aligned, surface-coloured with logo
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image
from ctk_markdown import CTkMarkdown

# Make sure the project root is on sys.path
_ROOT = Path(__file__).parent.parent.parent.parent

from config.settings import (
    COLOR_ACCENT,
    COLOR_AI_BUBBLE,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_USER_BUBBLE,
    FONT_FAMILY,
    FONT_SIZE_BODY,
)


class UserBubble(ctk.CTkFrame):
    """A right-aligned speech bubble for the user's messages with Markdown support."""

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

        self._markdown_view = CTkMarkdown(
            bubble,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color="transparent",
            border_width=0,
            activate_scrollbars=False,
            width=440,
        )
        self._markdown_view.pack(padx=16, pady=10)
        self._markdown_view.set_markdown(text)
        
        # Adjust height to content
        self._update_height()

        self.pack(fill="x", padx=12, pady=(8, 0))

    def _update_height(self) -> None:
        """Heuristic to adjust textbox height based on line count."""
        # Force update to get accurate text stats
        self._markdown_view.update_idletasks()
        # Count lines in the underlying textbox
        line_count = float(self._markdown_view.get("1.0", "end-1c").count("\n") + 1)
        # Approximate height: lines * line_height + some padding
        new_height = int(line_count * 22) + 10 
        self._markdown_view.configure(height=new_height)


class AssistantBubble(ctk.CTkFrame):
    """A left-aligned streaming bubble for Seneca's replies with Markdown support."""

    def __init__(self, parent: ctk.CTkScrollableFrame, on_update: Optional[Callable] = None) -> None:
        super().__init__(
            parent,
            fg_color="transparent",
        )
        self._on_update = on_update
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

        self._markdown_view = CTkMarkdown(
            self._bubble,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color="transparent",
            border_width=0,
            activate_scrollbars=False,
            width=440,
            height=30, # Start small
        )
        self._markdown_view.pack(padx=16, pady=10)

        self._text_buffer: list[str] = []

        self.pack(fill="x", padx=12, pady=(8, 0))

    def append_token(self, token: str) -> None:
        """Append *token* to the bubble text and adjust height."""
        self._text_buffer.append(token)
        full_text = "".join(self._text_buffer)
        self._markdown_view.set_markdown(full_text)
        self._update_height()
        if self._on_update:
            self._on_update()

    def _update_height(self) -> None:
        """Heuristic to adjust textbox height based on content."""
        self._markdown_view.update_idletasks()
        # Count total characters and estimate lines based on width (approx 60 chars per line at 440px)
        # plus actual newlines. This is more robust for streaming.
        text = self._markdown_view.get("1.0", "end-1c")
        lines = text.count("\n") + 1
        wrapped_lines = sum(max(1, len(line) // 65) for line in text.split("\n"))
        
        new_height = int(max(lines, wrapped_lines) * 22) + 10
        self._markdown_view.configure(height=new_height)

    def set_error(self, message: str) -> None:
        """Replace bubble content with an error message."""
        self._text_buffer = [message]
        self._markdown_view.set_markdown(message)
        self._markdown_view.configure(text_color="#e05c5c")
        self._update_height()
        if self._on_update:
            self._on_update()

    @property
    def full_text(self) -> str:
        """Return the complete assembled text."""
        return "".join(self._text_buffer)
