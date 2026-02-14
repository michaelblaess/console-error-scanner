"""Whitelist-Modell fuer bekannte Fehler die ignoriert werden sollen."""

from __future__ import annotations

import json
import logging
from fnmatch import fnmatch
from pathlib import Path

from .scan_result import ScanResult

logger = logging.getLogger(__name__)


class Whitelist:
    """Whitelist mit Wildcard-Patterns zum Filtern bekannter Fehler.

    Patterns verwenden fnmatch-Syntax:
        * = beliebig viele Zeichen
        ? = genau ein Zeichen
    Matching ist case-insensitive.
    """

    def __init__(self, patterns: list[str], path: str = "") -> None:
        """Erstellt eine Whitelist mit den gegebenen Patterns.

        Args:
            patterns: Liste von Wildcard-Patterns.
            path: Dateipfad der Whitelist (fuer Log-Ausgabe).
        """
        self.patterns = patterns
        self.path = path

    @staticmethod
    def load(path: str) -> Whitelist:
        """Laedt eine Whitelist aus einer JSON-Datei.

        Args:
            path: Pfad zur JSON-Datei.

        Returns:
            Geladene Whitelist-Instanz.

        Raises:
            FileNotFoundError: Wenn die Datei nicht existiert.
            json.JSONDecodeError: Wenn die Datei kein gueltiges JSON ist.
            ValueError: Wenn das JSON-Format ungueltig ist.
        """
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        if not isinstance(data, dict):
            raise ValueError(f"Whitelist-JSON muss ein Objekt sein, ist aber {type(data).__name__}")

        patterns = data.get("patterns", [])
        if not isinstance(patterns, list):
            raise ValueError(f"'patterns' muss eine Liste sein, ist aber {type(patterns).__name__}")

        # Nur Strings akzeptieren
        valid_patterns = []
        for idx, pattern in enumerate(patterns):
            if isinstance(pattern, str) and pattern.strip():
                valid_patterns.append(pattern.strip())
            else:
                logger.warning("Whitelist: Ungueltige Pattern an Index %d uebersprungen: %r", idx, pattern)

        return Whitelist(patterns=valid_patterns, path=str(file_path.resolve()))

    def is_whitelisted(self, message: str) -> bool:
        """Prueft ob eine Fehlermeldung von einem Whitelist-Pattern abgedeckt wird.

        Args:
            message: Die zu pruefende Fehlermeldung.

        Returns:
            True wenn die Meldung einem Pattern entspricht.
        """
        if not message or not self.patterns:
            return False

        message_lower = message.lower()
        return any(fnmatch(message_lower, pattern.lower()) for pattern in self.patterns)

    def apply(self, result: ScanResult) -> int:
        """Markiert gematchte Errors in einem ScanResult als whitelisted.

        Args:
            result: Das ScanResult dessen Errors geprueft werden sollen.

        Returns:
            Anzahl der neu als whitelisted markierten Errors.
        """
        count = 0
        for error in result.errors:
            if not error.whitelisted and self.is_whitelisted(error.message):
                error.whitelisted = True
                count += 1
        return count

    def __len__(self) -> int:
        """Anzahl der Patterns."""
        return len(self.patterns)

    def __repr__(self) -> str:
        return f"Whitelist({len(self.patterns)} patterns, path={self.path!r})"
