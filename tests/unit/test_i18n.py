"""
tests/unit/test_i18n.py – Unit tests for the I18n locale helper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from seneca.i18n.locale import I18n


class TestI18n:
    def test_spanish_translation(self):
        i18n = I18n("es_ES")
        assert i18n.t("new_conversation") == "Nueva conversación"

    def test_english_translation(self):
        i18n = I18n("en_US")
        assert i18n.t("new_conversation") == "New conversation"

    def test_french_translation(self):
        i18n = I18n("fr_FR")
        assert i18n.t("placeholder") == "Tapez un message…"

    def test_unknown_locale_falls_back_to_english(self):
        i18n = I18n("xx_XX")
        assert i18n.t("conversations") == "Conversations"

    def test_unknown_key_returns_key(self):
        i18n = I18n("en_US")
        assert i18n.t("nonexistent_key") == "nonexistent_key"

    def test_locale_tag_property(self):
        i18n = I18n("de_DE")
        assert i18n.locale_tag == "de_DE"
