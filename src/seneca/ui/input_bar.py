"""
src/seneca/ui/input_bar.py – Bottom input bar with mic and send controls.

Layout (right panel, bottom 15 %):
  ┌─────────────────────────────────────────────┐
  │  Text area (multiline)           🎤  ▶ / ■  │
  └─────────────────────────────────────────────┘

The play icon (▶) transitions to a stop icon (■) while Seneca is
thinking.  The text area expands to fill all horizontal space except
the two icon buttons.
"""
# src/seneca/ui/input_bar.py

import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from typing import Callable
import logging

import customtkinter as ctk
from PIL import Image, ImageTk

# Make sure the project root is on sys.path when running from src/
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_STOP,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_SIZE_BODY,
)
from seneca.utils import audio
from seneca.utils.Desktop.Windows import text_to_editor

logger = logging.getLogger(__name__)


class ToolMenu(ctk.CTkToplevel):
    """Custom context menu for tools with matching aesthetics."""

    def __init__(self, master, items, x, y):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLOR_SURFACE)

        self.frame = ctk.CTkFrame(
            self,
            fg_color=COLOR_SURFACE,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=10,
        )
        self.frame.pack(fill="both", expand=True)

        for label, icon, command in items:
            btn = ctk.CTkButton(
                self.frame,
                text=f"  {label}",
                image=icon,
                compound="left",
                anchor="w",
                fg_color="transparent",
                hover_color=COLOR_BORDER,
                text_color=COLOR_TEXT_PRIMARY,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BODY),
                height=34,
                corner_radius=6,
                command=lambda cmd=command: self._on_click(cmd),
            )
            btn.pack(fill="x", padx=6, pady=3)

        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        # Position slightly above the button
        self.geometry(f"{width}x{height}+{x}+{y - height - 12}")

        self.bind("<FocusOut>", lambda e: self.destroy())
        self.after(10, self.focus_set)
        self.after(10, self.grab_set)

    def _on_click(self, command: Callable):
        command()
        self.destroy()


class InputBar(ctk.CTkFrame):
    """
    Composite widget: multiline text entry + mic button + send/stop button.

    Callbacks
    ---------
    on_submit(text) – called when the user clicks ▶ with non-empty text.
    on_cancel()     – called when the user clicks ■ (stop).
    on_tool_added(tool_func) - called when a tool is selected from the menu.
    on_tool_removed(tool_func) - called when a tool is removed by clicking its button.
    """

    DEFAULT_ICON_SIZE = 26

    DEFAULT_BUTTON_SIZE = 36
    DEFAULT_BUTTON_CORNER_RADIUS = 18

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
        on_tool_added: Callable[[Callable], None] = None,
        on_tool_removed: Callable[[Callable], None] = None,
        can_add_tools_func: Callable[[], bool] = lambda: True,
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
        self._on_tool_added = on_tool_added
        self._on_tool_removed = on_tool_removed
        self._can_add_tools_func = can_add_tools_func
        self._placeholder = placeholder
        self._thinking = False
        self._tool_buttons: list[ctk.CTkButton] = []

        self._load_icons()
        self._build()

    def _load_icons(self) -> None:
        """Load icon images for the buttons."""
        icons_dir = _ROOT / "assets" / "icons"

        # Load and resize icons (assuming standard size around 20x20 for button icons)
        self._icon_play = ctk.CTkImage(
            light_image=Image.open(icons_dir / "play.png"),
            dark_image=Image.open(icons_dir / "play-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE),
        )
        self._icon_stop = ctk.CTkImage(
            light_image=Image.open(icons_dir / "stop.png"),
            dark_image=Image.open(icons_dir / "stop-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE),
        )
        self._icon_mic = ctk.CTkImage(
            light_image=Image.open(icons_dir / "micro.png"),
            dark_image=Image.open(icons_dir / "micro-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE),
        )

        self._icon_add = ctk.CTkImage(
            light_image=Image.open(icons_dir / "add-black.png"),
            dark_image=Image.open(icons_dir / "add-white.png"),
            size=(self.DEFAULT_ICON_SIZE, self.DEFAULT_ICON_SIZE),
        )

        # Tool icons
        self._icon_notepad = ctk.CTkImage(
            light_image=Image.open(icons_dir / "windows-notepad-icon-black.png"),
            dark_image=Image.open(icons_dir / "windows-notepad-icon-white.png"),
            size=(20, 20),
        )
        self._icon_writer = ctk.CTkImage(
            light_image=Image.open(icons_dir / "libreoffice-writer-logo.wine.png"),
            dark_image=Image.open(icons_dir / "libreoffice-writer-logo.wine-white.png"),
            size=(20, 20),
        )

    # ── Construction ──────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Container for add button and tool buttons
        self._left_btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self._can_add_tools_func():
            self._left_btn_frame.grid(row=0, column=0, padx=(8, 0), pady=8, sticky="sw")

        # Add button
        self._add_btn = ctk.CTkButton(
            self._left_btn_frame,
            text="",
            image=self._icon_add,
            width=self.DEFAULT_BUTTON_SIZE,
            height=self.DEFAULT_BUTTON_SIZE,
            corner_radius=self.DEFAULT_BUTTON_CORNER_RADIUS,
            fg_color="transparent",
            hover_color=COLOR_BORDER,
            command=self._on_add_click,
        )
        self._add_btn.pack(side="left")

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
        # Adjust padx based on whether add button is visible
        text_padx_left = 4 if self._can_add_tools_func() else 12
        self._text.grid(
            row=0, column=1, padx=(text_padx_left, 4), pady=8, sticky="nsew"
        )
        self._text.bind("<Return>", self._on_return)
        self._text.bind("<Shift-Return>", lambda e: None)  # allow newline
        self._text.bind("<FocusIn>", self._on_text_focus_in)
        self._text.bind("<FocusOut>", self._on_text_focus_out)
        self._show_placeholder()

        # Button frame (right side, bottom-aligned)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(0, 8), pady=8, sticky="se")

        # Microphone button
        self._mic_btn = ctk.CTkButton(
            btn_frame,
            text="",
            image=self._icon_mic,
            width=self.DEFAULT_BUTTON_SIZE,
            height=self.DEFAULT_BUTTON_SIZE,
            corner_radius=self.DEFAULT_BUTTON_CORNER_RADIUS,
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
            width=self.DEFAULT_BUTTON_SIZE,
            height=self.DEFAULT_BUTTON_SIZE,
            corner_radius=self.DEFAULT_BUTTON_CORNER_RADIUS,
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

    def _on_text_focus_in(self, event=None) -> None:
        """Clear placeholder text when the textbox gains focus."""
        logger.debug(f"FocusIn event. Current text: '{self._text.get('1.0', 'end-1c').strip()}', Placeholder: '{self._placeholder.strip()}'")
        if self._text.get("1.0", "end-1c").strip() == self._placeholder.strip():
            self._text.delete("1.0", "end")
            self._text.configure(text_color=COLOR_TEXT_PRIMARY)
            logger.debug("Placeholder cleared.")

    def _on_text_focus_out(self, event=None) -> None:
        """Show placeholder text when the textbox loses focus and is empty."""
        logger.debug(f"FocusOut event. Current text: '{self._text.get('1.0', 'end-1c').strip()}'")
        if not self._text.get("1.0", "end-1c").strip():
            self._show_placeholder()
            logger.debug("Placeholder shown.")

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
        self._on_text_focus_in() # Use the focus-in logic to clear if placeholder is present
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)

    def _on_add_click(self) -> None:
        """Show a custom menu with tools, only if supported by the model."""
        if not self._can_add_tools_func():
            return

        items = []

        if os.name == "nt":
            # Windows: Notepad and Writer
            items.append(
                (
                    "Notepad",
                    self._icon_notepad,
                    lambda: self._add_tool_ui(
                        "Notepad",
                        self._icon_notepad,
                        text_to_editor.save_and_open_with_notepad,
                    ),
                )
            )

            # Default path for Writer on Windows as per text_to_editor.py
            swriter_path = r"C:\Program Files (x86)\OpenOffice 4\program\swriter.exe"
            if os.path.exists(swriter_path):
                items.append(
                    (
                        "Writer",
                        self._icon_writer,
                        lambda: self._add_tool_ui(
                            "Writer",
                            self._icon_writer,
                            text_to_editor.save_and_open_with_swriter,
                        ),
                    )
                )
        else:
            # Linux: Kate and Writer
            items.append(
                (
                    "Kate",
                    self._icon_notepad,
                    lambda: self._add_tool_ui(
                        "Kate",
                        self._icon_notepad,
                        text_to_editor.save_text_to_file,
                    ),
                )
            )

            if shutil.which("swriter"):
                items.append(
                    (
                        "Writer",
                        self._icon_writer,
                        lambda: self._add_tool_ui(
                            "Writer",
                            self._icon_writer,
                            text_to_editor.save_and_open_with_swriter,
                        ),
                    )
                )

        if not items:
            return

        x = self._add_btn.winfo_rootx()
        y = self._add_btn.winfo_rooty()
        ToolMenu(self, items, x, y)

    def _add_tool_ui(
        self, label: str, icon: ctk.CTkImage, tool_func: Callable
    ) -> None:
        """Add a tool button to the UI and notify the agent."""
        # Check if already added
        for btn in self._tool_buttons:
            if getattr(btn, "_tool_label", "") == label:
                return

        tool_btn = ctk.CTkButton(
            self._left_btn_frame,
            text="",
            image=icon,
            width=self.DEFAULT_BUTTON_SIZE,
            height=self.DEFAULT_BUTTON_SIZE,
            corner_radius=self.DEFAULT_BUTTON_CORNER_RADIUS,
            fg_color=COLOR_SURFACE_ALT,
            hover_color=COLOR_STOP,  # Visual hint for removal
            command=lambda: self._remove_tool_ui(tool_btn, tool_func),
        )
        tool_btn._tool_label = label  # Tag it for deduplication
        tool_btn.pack(side="left", padx=(4, 0))
        self._tool_buttons.append(tool_btn)

        if self._on_tool_added:
            self._on_tool_added(tool_func)

    def _remove_tool_ui(self, button: ctk.CTkButton, tool_func: Callable) -> None:
        """Remove a tool button and notify the agent."""
        if button in self._tool_buttons:
            self._tool_buttons.remove(button)
        button.destroy()

        if self._on_tool_removed:
            self._on_tool_removed(tool_func)

    # ── Public API ────────────────────────────────────────────────────────

    def set_thinking(self, thinking: bool) -> None:
        """Switch between ▶ (send) and ■ (stop) mode."""
        self._thinking = thinking
        if thinking:
            self._send_btn.configure(
                text="",
                image=self._icon_stop,
                fg_color=COLOR_STOP,
                hover_color="#c04040",
            )
            self._text.configure(state="disabled")
        else:
            self._send_btn.configure(
                text="",
                image=self._icon_play,
                fg_color=COLOR_ACCENT,
                hover_color="#3a7ae0",
            )
            self._text.configure(state="normal")
            self.clear() # Call clear to empty the text area

    def clear(self) -> None:
        """Clear the text box and set text color to primary."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(text_color=COLOR_TEXT_PRIMARY) # Ensure text color is primary for new input

    def clear_tools(self) -> None:
        """Remove all active tool buttons."""
        for btn in self._tool_buttons:
            btn.destroy()
        self._tool_buttons.clear()

    def set_placeholder(self, text: str) -> None:
        """Update the placeholder string (e.g. for locale changes)."""
        self._placeholder = text
        self._show_placeholder()