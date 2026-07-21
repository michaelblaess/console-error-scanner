"""Sichert die schonenden Vorgabewerte und die Sprachwahl ab.

Diese Tests halten die Zusicherung fest, dass ein Scan ohne weitere Angaben
gedrosselt ist und robots.txt beachtet - und dass beim Erststart niemand einen
Rechtstext in einer fremden Sprache vorgesetzt bekommt.
"""

from __future__ import annotations

import locale

from console_error_scanner.i18n import detect_language
from console_error_scanner.models.settings import Settings
from console_error_scanner.services.rate_limit import RateLimiter
from console_error_scanner.services.scanner import Scanner


class TestSafeDefaults:
    def test_scanner_is_throttled_by_default(self) -> None:
        assert Scanner().rate_per_minute == 60

    def test_scanner_limiter_is_active_by_default(self) -> None:
        assert RateLimiter(Scanner().rate_per_minute).enabled is True

    def test_settings_enable_the_rate_limit(self) -> None:
        assert Settings().rate_limit_enabled is True

    def test_settings_default_rate(self) -> None:
        assert Settings().rate_per_minute == 60

    def test_robots_is_respected_by_default(self) -> None:
        assert Settings().respect_robots is True

    def test_rate_settings_survive_the_dict_roundtrip(self) -> None:
        settings = Settings()
        settings.rate_per_minute = 20
        settings.rate_limit_enabled = False
        data = settings.to_dict()
        assert data["rate_per_minute"] == 20
        assert data["rate_limit_enabled"] is False


class TestLanguageDetection:
    def test_german_environment(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(locale, "getlocale", lambda *a: ("de_DE", "UTF-8"))
        assert detect_language() == "de"

    def test_austrian_environment_is_german_too(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(locale, "getlocale", lambda *a: ("de_AT", "UTF-8"))
        assert detect_language() == "de"

    def test_english_environment(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(locale, "getlocale", lambda *a: ("en_US", "UTF-8"))
        assert detect_language() == "en"

    def test_other_language_falls_back_to_english(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(locale, "getlocale", lambda *a: ("pt_BR", "UTF-8"))
        assert detect_language() == "en"

    def test_broken_locale_falls_back_to_english(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """locale.getlocale() wirft auf manchen Systemen ValueError."""

        def boom(*args: object) -> tuple[str, str]:
            raise ValueError("unknown locale")

        monkeypatch.setattr(locale, "getlocale", boom)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        assert detect_language() == "en"


class TestLocaleFiles:
    def test_both_languages_have_the_same_keys(self) -> None:
        import json
        from pathlib import Path

        base = Path(__file__).resolve().parent.parent / "src" / "console_error_scanner" / "locale"
        de = json.loads((base / "de.json").read_text(encoding="utf-8"))
        en = json.loads((base / "en.json").read_text(encoding="utf-8"))
        assert set(de) == set(en)
