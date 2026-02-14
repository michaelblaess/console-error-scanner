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


@dataclass
class Settings:
    """Persistierte Benutzereinstellungen.

    Attributes:
        theme: Name des Textual-Themes.
        accept_consent: Consent-Akzeptierung aktiv.
    """

    theme: str = "textual-dark"
    accept_consent: bool = True

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
        }

    @staticmethod
    def load() -> Settings:
        """Laedt die Einstellungen aus der JSON-Datei.

        Gibt Default-Einstellungen zurueck bei Fehler oder fehlender Datei.

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
            return Settings(
                theme=data.get("theme", "textual-dark"),
                accept_consent=data.get("accept_consent", True),
            )
        except Exception as exc:
            logger.warning("Settings konnten nicht geladen werden: %s", exc)
            return Settings()

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
