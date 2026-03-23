"""
main.py – Seneca-AI entry point.

Run from the project root:

    python main.py

or, after installing the package in editable mode:

    seneca
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ── Launch ────────────────────────────────────────────────────────────────
from seneca.ui.main_window import MainWindow  # noqa: E402


def main() -> None:
    """Create and run the Seneca-AI main window."""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
