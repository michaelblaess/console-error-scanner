"""Whitelist-Modell fuer bekannte Fehler die ignoriert werden sollen."""

from __future__ import annotations

import contextlib
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

    def reclassify(self, result: ScanResult) -> None:
        """Setzt das whitelisted-Flag ALLER Errors neu (beide Richtungen).

        Anders als ``apply`` (nur False->True) wird hier auch zurueckgesetzt -
        noetig nachdem ein Pattern entfernt wurde, damit vorher unterdrueckte
        Fehler wieder als Fehler erscheinen.

        Args:
            result:
                Das ScanResult dessen Errors neu klassifiziert werden.
        """
        for error in result.errors:
            error.whitelisted = self.is_whitelisted(error.message)

    @staticmethod
    def pattern_for_message(message: str) -> str:
        """Leitet ein fnmatch-Pattern aus einer Fehlermeldung ab.

        Nimmt die erste Zeile (Stack-Traces ignorieren) und umschliesst sie mit
        ``*`` - die fnmatch-Sonderzeichen ``[ * ?`` werden literal entschaerft,
        damit das Pattern die Meldung woertlich matcht. Das Ergebnis ist als
        Startpunkt gedacht und kann im Whitelist-Editor verfeinert werden.

        Args:
            message:
                Die Fehlermeldung.

        Returns:
            Ein fnmatch-Pattern (z.B. ``*App X has not been started*``) oder "".
        """
        first = (message or "").split("\n", 1)[0].strip()
        if not first:
            return ""
        # Reihenfolge wichtig: zuerst '[' escapen (fuegt selbst '[]' ein).
        first = first.replace("[", "[[]").replace("*", "[*]").replace("?", "[?]")
        return f"*{first}*"

    def add_pattern(self, pattern: str) -> bool:
        """Fuegt ein Pattern hinzu (wenn noch nicht vorhanden).

        Args:
            pattern:
                Das fnmatch-Pattern.

        Returns:
            True wenn neu hinzugefuegt, False wenn bereits vorhanden/leer.
        """
        pattern = pattern.strip()
        if not pattern or pattern in self.patterns:
            return False
        self.patterns.append(pattern)
        return True

    def patterns_matching(self, message: str) -> list[str]:
        """Liefert alle Patterns, die eine Meldung matchen (Reihenfolge erhalten).

        Args:
            message:
                Die zu pruefende Meldung.

        Returns:
            Liste der matchenden Patterns.
        """
        if not message:
            return []
        message_lower = message.lower()
        return [p for p in self.patterns if fnmatch(message_lower, p.lower())]

    def remove_pattern(self, pattern: str) -> bool:
        """Entfernt ein exaktes Pattern.

        Args:
            pattern:
                Das zu entfernende Pattern.

        Returns:
            True wenn entfernt, False wenn nicht vorhanden.
        """
        if pattern not in self.patterns:
            return False
        self.patterns = [p for p in self.patterns if p != pattern]
        return True

    def remove_patterns_matching(self, message: str) -> list[str]:
        """Entfernt alle Patterns, die eine bestimmte Meldung matchen.

        Args:
            message:
                Die Fehlermeldung, deren matchende Patterns entfernt werden.

        Returns:
            Liste der entfernten Patterns.
        """
        if not message:
            return []
        message_lower = message.lower()
        removed = [p for p in self.patterns if fnmatch(message_lower, p.lower())]
        if removed:
            self.patterns = [p for p in self.patterns if p not in removed]
        return removed

    def save(self) -> None:
        """Schreibt die Patterns zurueck in die JSON-Datei (``self.path``).

        Eine vorhandene ``description`` bleibt erhalten. Raises wenn kein Pfad
        gesetzt ist.
        """
        if not self.path:
            raise ValueError("Whitelist hat keinen Pfad - kann nicht gespeichert werden")
        file_path = Path(self.path)
        description = "Known Bugs - diese Fehler werden ignoriert"
        if file_path.is_file():
            with contextlib.suppress(Exception):
                existing = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(existing, dict) and isinstance(existing.get("description"), str):
                    description = existing["description"]
        payload = {"description": description, "patterns": self.patterns}
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def __len__(self) -> int:
        """Anzahl der Patterns."""
        return len(self.patterns)

    def __repr__(self) -> str:
        return f"Whitelist({len(self.patterns)} patterns, path={self.path!r})"
