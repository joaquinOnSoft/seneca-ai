"""
config/settings.py – Application-wide configuration constants.

All tuneable values live here so that the rest of the code-base
never contains magic literals.
"""

# ── Appearance ────────────────────────────────────────────────────────────
APP_TITLE: str = "Seneca-AI"
THEME: str = "dark"          # "dark" | "light" | "system"
COLOR_THEME: str = "blue"    # customtkinter built-in palette

# Main palette (dark mode)
COLOR_BG: str = "#0f1117"
COLOR_SIDEBAR: str = "#161b27"
COLOR_SURFACE: str = "#1e2333"
COLOR_SURFACE_ALT: str = "#252b3d"
COLOR_BORDER: str = "#2e3650"
COLOR_ACCENT: str = "#4f8ef7"
COLOR_ACCENT_HOVER: str = "#6fa3ff"
COLOR_TEXT_PRIMARY: str = "#e8eaf0"
COLOR_TEXT_SECONDARY: str = "#7a84a0"
COLOR_USER_BUBBLE: str = "#1a3a6b"
COLOR_AI_BUBBLE: str = "#1e2333"
COLOR_STOP: str = "#e05c5c"

# ── Typography ────────────────────────────────────────────────────────────
FONT_FAMILY: str = "Inter"
FONT_SIZE_TITLE: int = 14
FONT_SIZE_BODY: int = 13
FONT_SIZE_SMALL: int = 11

# ── Layout ────────────────────────────────────────────────────────────────
SIDEBAR_WIDTH: int = 240
SIDEBAR_ANIMATION_MS: int = 180
INPUT_HEIGHT_RATIO: float = 0.15   # 15 % of window height
INPUT_MARGIN_BOTTOM: int = 10
INPUT_MARGIN_RIGHT: int = 10
BUBBLE_MAX_WIDTH_RATIO: float = 0.70
BUBBLE_PAD_X: int = 16
BUBBLE_PAD_Y: int = 10
BUBBLE_RADIUS: int = 16

# ── Conversation ──────────────────────────────────────────────────────────
MAX_CONVERSATIONS: int = 20
