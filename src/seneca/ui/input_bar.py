"""
src/seneca/ui/input_bar.py – Bottom input bar with mic and send controls.

Layout (right panel, bottom 15 %):
  ┌─────────────────────────────────────────────┐
  │  Text area (multiline)          🎤  ▶ / ■  │
  └─────────────────────────────────────────────┘

The play icon (▶) transitions to a stop icon (■) while Seneca is
thinking.  The text area expands to fill all horizontal space except
the two icon buttons.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from PIL import Image

# Make sure the project root is on sys.path when running from src/
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_BG,
    COLOR_STOP,
    COLOR_SURFACE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_SIZE_BODY,
)
from seneca.utils import audio


class InputBar(ctk.CTkFrame):
    """
    Composite widget: multiline text entry + mic button + send/stop button.

    Callbacks
    ---------
    on_submit(text) – called when the user clicks ▶ with non-empty text.
    on_cancel()     – called when the user clicks ■ (stop).
    """

    DEFAULT_ICON_SIZE = 25

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
        placeholder: str = "Type a message…",
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            fg_color=COLOR_SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER,
            **kwargs,
        )
        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._placeholder = placeholder
        self._thinking = False

        self._load_icons()
        self._build()

    def _load_icons(self) -> None:
        """Load icon images for the buttons."""
        icons_dir = _ROOT / "assets" / "icons"
        
        # Load and resize icons (assuming standard size around 20x20 for button icons)
        self._icon_play = ctk.CTkImage(
            light_image=Image.open(icons_dir / "play.png"),
            dark_image=Image.open(icons_dir / "play-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE)
        )
        self._icon_stop = ctk.CTkImage(
            light_image=Image.open(icons_dir / "stop.png"),
            dark_image=Image.open(icons_dir / "stop-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE)
        )
        self._icon_mic = ctk.CTkImage(
            light_image=Image.open(icons_dir / "micro.png"),
            dark_image=Image.open(icons_dir / "micro-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE)
        )

    # ── Construction ──────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Multiline text widget (native tk.Text wrapped in CTk style)
        self._text = ctk.CTkTextbox(
            self,
            fg_color="transparent",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BODY),
            text_color=COLOR_TEXT_PRIMARY,
            border_width=0,
            wrap="word",
            activate_scrollbars=False,
        )
        self._text.grid(
            row=0, column=0, padx=(12, 4), pady=8, sticky="nsew"
        )
        self._text.bind("<Return>", self._on_return)
        self._text.bind("<Shift-Return>", lambda e: None)  # allow newline
        self._show_placeholder()

        # Button frame (right side, bottom-aligned)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="se")

        # Microphone button
        self._mic_btn = ctk.CTkButton(
            btn_frame,
            text="",
            image=self._icon_mic,
            width=36,
            height=36,
            corner_radius=18,
            fg_color="transparent",
            hover_color=COLOR_BORDER,
            font=ctk.CTkFont(size=16),
            command=self._on_mic,
        )
        self._mic_btn.pack(side="left", padx=(0, 6))

        # Send / Stop button
        self._send_btn = ctk.CTkButton(
            btn_frame,
            text="",  # No text, just icon
            image=self._icon_play,
            width=36,
            height=36,
            corner_radius=18,
            fg_color=COLOR_ACCENT,
            hover_color="#3a7ae0",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_send_or_stop,
        )
        self._send_btn.pack(side="left")

    # ── Placeholder helpers ───────────────────────────────────────────────

    def _show_placeholder(self) -> None:
        self._text.delete("1.0", "end")
        self._text.insert("1.0", self._placeholder)
        self._text.configure(text_color=COLOR_TEXT_SECONDARY)
        self._text.bind("<FocusIn>", self._clear_placeholder)

    def _clear_placeholder(self, _event=None) -> None:
        if self._text.get("1.0", "end-1c") == self._placeholder:
            self._text.delete("1.0", "end")
            self._text.configure(text_color=COLOR_TEXT_PRIMARY)
        self._text.unbind("<FocusIn>")

    # ── Event handlers ────────────────────────────────────────────────────

    def _on_return(self, event) -> str:
        """Submit on plain Enter; allow Shift-Enter for newlines."""
        if not event.state & 0x1:  # Shift not held
            self._on_send_or_stop()
            return "break"
        return ""

    def _on_send_or_stop(self) -> None:
        if self._thinking:
            self._on_cancel()
            return
        text = self._text.get("1.0", "end-1c").strip()
        if not text or text == self._placeholder:
            return
        self._on_submit(text)

    def _on_mic(self) -> None:
        if not audio.is_available():
            return
        self._mic_btn.configure(fg_color=COLOR_ACCENT)
        audio.listen_once(
            on_result=self._on_speech_result,
            on_error=self._on_speech_error,
        )

    def _on_speech_result(self, text: str) -> None:
        self.after(0, lambda: self._inject_text(text))
        self.after(0, lambda: self._mic_btn.configure(fg_color="transparent"))

    def _on_speech_error(self, _msg: str) -> None:
        self.after(0, lambda: self._mic_btn.configure(fg_color="transparent"))

    def _inject_text(self, text: str) -> None:
        self._clear_placeholder()
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)

    # ── Public API ────────────────────────────────────────────────────────

    def set_thinking(self, thinking: bool) -> None:
        """Switch between ▶ (send) and ■ (stop) mode."""
        self._thinking = thinking
        if thinking:
            self._send_btn.configure(
                text="", image=self._icon_stop, fg_color=COLOR_STOP, hover_color="#c04040"
            )
            self._text.configure(state="disabled")
        else:
            self._send_btn.configure(
                text="", image=self._icon_play, fg_color=COLOR_ACCENT, hover_color="#3a7ae0"
            )
            self._text.configure(state="normal")
            self.clear()

    def clear(self) -> None:
        """Clear the text box and restore the placeholder."""
        self._text.configure(state="normal")
        self._show_placeholder()

    def set_placeholder(self, text: str) -> None:
        """Update the placeholder string (e.g. for locale changes)."""
        self._placeholder = text
        self._show_placeholder()
