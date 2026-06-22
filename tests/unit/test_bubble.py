"""
tests/unit/test_bubble.py – Unit tests for UserBubble and AssistantBubble.
"""

import sys
import tkinter as tk
from pathlib import Path
import customtkinter as ctk
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from seneca.ui.bubble import UserBubble, AssistantBubble


class TestBubbles:
    @pytest.fixture(autouse=True)
    def setup_tk(self):
        self.root = ctk.CTk()
        self.frame = ctk.CTkScrollableFrame(self.root)
        self.frame.pack()
        yield
        self.root.destroy()

    def test_user_bubble_height_update(self):
        bubble = UserBubble(self.frame, "Hello World")
        # Ensure it has been configured with some height
        height = bubble._markdown_view.cget("height")
        assert height > 0

        # Test height updates for longer text
        bubble._markdown_view.set_markdown("Hello World\nLine 2\nLine 3\nLine 4")
        bubble._update_height()
        height_after = bubble._markdown_view.cget("height")
        assert height_after > height

    def test_assistant_bubble_height_update(self):
        bubble = AssistantBubble(self.frame)
        bubble.append_token("Hello")
        height_initial = bubble._markdown_view.cget("height")

        # Stream more text
        bubble.append_token(
            " World\nThis is a test message to verify the dynamic height update "
            "mechanism for Seneca AI's assistant chat bubble."
        )
        height_after = bubble._markdown_view.cget("height")
        assert height_after > height_initial
