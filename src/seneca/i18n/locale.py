"""
src/seneca/i18n/locale.py – Internationalisation helpers via Babel.

Exposes a small catalogue of UI strings keyed by locale.  For a
production app this would load from .po/.mo files; here we use a
plain dict for simplicity while the Babel dependency is already
declared for future expansion.
"""

from __future__ import annotations

from babel import Locale

# Minimal UI string catalogue  {locale_tag: {key: translation}}
_CATALOGUE: dict[str, dict[str, str]] = {
    "es_ES": {
        "app_title": "Seneca AI",
        "new_conversation": "Nueva conversación",
        "conversations": "Conversaciones",
        "placeholder": "Escribe un mensaje…",
        "mic_unavailable": "Micrófono no disponible",
        "thinking": "Seneca está pensando…",
        "error_prefix": "Error",
    },
    "en_US": {
        "app_title": "Seneca AI",
        "new_conversation": "New conversation",
        "conversations": "Conversations",
        "placeholder": "Type a message…",
        "mic_unavailable": "Microphone not available",
        "thinking": "Seneca is thinking…",
        "error_prefix": "Error",
    },
    "fr_FR": {
        "app_title": "Seneca AI",
        "new_conversation": "Nouvelle conversation",
        "conversations": "Conversations",
        "placeholder": "Tapez un message…",
        "mic_unavailable": "Microphone indisponible",
        "thinking": "Seneca réfléchit…",
        "error_prefix": "Erreur",
    },
    "de_DE": {
        "app_title": "Seneca AI",
        "new_conversation": "Neues Gespräch",
        "conversations": "Gespräche",
        "placeholder": "Nachricht eingeben…",
        "mic_unavailable": "Mikrofon nicht verfügbar",
        "thinking": "Seneca denkt nach…",
        "error_prefix": "Fehler",
    },
}

_FALLBACK = "en_US"


class I18n:
    """Lightweight internationalisation helper."""

    def __init__(self, locale_tag: str = "en_US") -> None:
        try:
            Locale.parse(locale_tag, sep="_")
            self._tag = locale_tag
        except Exception:
            self._tag = _FALLBACK

        self._strings = _CATALOGUE.get(self._tag, _CATALOGUE[_FALLBACK])

    def t(self, key: str) -> str:  # noqa: D401
        """Return the translation for *key*, falling back to the key itself."""
        return self._strings.get(key, key)

    @property
    def locale_tag(self) -> str:
        """Active locale tag, e.g. ``'es_ES'``."""
        return self._tag
