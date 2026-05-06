"""Persistierte Einstellungen fuer Console Error Scanner.

Speichert und laedt Benutzereinstellungen aus
~/.console-error-scanner/settings.json.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# textual-themes 0.5 hat 25 Themes umbenannt (trademark-safety pass).
# Settings-Files aelterer Versionen koennen alte Slugs gespeichert haben —
# die werden beim Laden transparent gemappt.
_LEGACY_THEME_MAP: dict[str, str] = {
    "c64": "brotkasten",
    "amiga": "boing",
    "atari-st": "gemstone",
    "ibm-terminal": "classic-terminal",
    "nextstep": "next",
    "beos": "bebox",
    "ubuntu": "bunty",
    "macos": "cupertino",
    "windows-xp": "luna",
    "msdos": "commandr",
    "solaris-cde": "motif",
    "os2-warp": "warp",
    "opensuse": "geeko",
    "linux-mint": "minty",
    "red-hat": "crimson",
    "raspberry-pi": "razzy",
    "freebsd": "beastie",
    "tudor": "fifty-eight",
    "goldfinger": "goldfinder",
    "hulk": "hulkula",
    "batman": "flughund",
    "gameboy": "brick",
    "pan-am": "clipper",
    "miami-vice": "miami",
    "martini-racing": "racing",
    "superman": "metropolis",
    "spiderman": "spiderized",
    "gulf-racing": "textual-dark",  # entferntes Theme -> Textual Default
}


@dataclass
class Settings:
    """Persistierte Benutzereinstellungen.

    Attributes:
        theme: Name des Textual-Themes.
        accept_consent: Consent-Akzeptierung aktiv.
    """

    theme: str = "textual-dark"
    accept_consent: bool = True
    trigger_lazy_load: bool = True
    language: str = "de"

    SETTINGS_DIR = Path.home() / ".console-error-scanner"
    SETTINGS_FILE = SETTINGS_DIR / "settings.json"

    def to_dict(self) -> dict:
        """Konvertiert die Einstellungen in ein Dictionary fuer JSON.

        Returns:
            Dictionary mit allen Feldern.
        """
        return {
            "theme": self.theme,
            "accept_consent": self.accept_consent,
            "trigger_lazy_load": self.trigger_lazy_load,
            "language": self.language,
        }

    @staticmethod
    def load() -> Settings:
        """Laedt die Einstellungen aus der JSON-Datei.

        Gibt Default-Einstellungen zurueck bei Fehler oder fehlender Datei.
        Migriert dabei alte Theme-Slugs aus textual-themes < 0.5 auf
        ihre aktuellen Namen und persistiert die Migration.

        Returns:
            Settings-Objekt.
        """
        if not Settings.SETTINGS_FILE.is_file():
            return Settings()

        try:
            raw = Settings.SETTINGS_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return Settings()
            settings = Settings(
                theme=data.get("theme", "textual-dark"),
                accept_consent=data.get("accept_consent", True),
                trigger_lazy_load=data.get("trigger_lazy_load", True),
                language=data.get("language", "de"),
            )
        except Exception as exc:
            logger.warning("Settings konnten nicht geladen werden: %s", exc)
            return Settings()

        # Legacy-Theme-Slug migrieren
        if settings.theme in _LEGACY_THEME_MAP:
            settings.theme = _LEGACY_THEME_MAP[settings.theme]
            settings.save()

        return settings

    def save(self) -> None:
        """Speichert die Einstellungen in die JSON-Datei.

        Erstellt das Verzeichnis falls es nicht existiert.
        """
        try:
            Settings.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            Settings.SETTINGS_FILE.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Settings konnten nicht gespeichert werden: %s", exc)
