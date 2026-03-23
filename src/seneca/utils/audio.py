"""
src/seneca/utils/audio.py – Microphone / speech-to-text utilities.

Uses the SpeechRecognition library with Google Web Speech as the
default backend.  The heavy lifting runs in a daemon thread so the
UI stays responsive.
"""

from __future__ import annotations

import threading
from typing import Callable

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False


def is_available() -> bool:
    """Return *True* if speech recognition dependencies are present."""
    return _SR_AVAILABLE


def listen_once(
    on_result: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """
    Record one utterance from the default microphone and call
    *on_result* with the transcribed text, or *on_error* with a
    human-readable message.

    Runs in a background daemon thread; returns immediately.
    """
    if not _SR_AVAILABLE:
        on_error("SpeechRecognition library not installed.")
        return

    def _worker() -> None:
        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=10)
            text: str = recognizer.recognize_google(audio)
            on_result(text)
        except sr.WaitTimeoutError:
            on_error("No speech detected. Please try again.")
        except sr.UnknownValueError:
            on_error("Could not understand audio. Please try again.")
        except sr.RequestError as exc:
            on_error(f"Speech service error: {exc}")
        except OSError as exc:
            on_error(f"Microphone error: {exc}")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
