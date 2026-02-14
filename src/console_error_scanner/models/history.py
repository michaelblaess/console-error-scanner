"""History-Modell fuer Console Error Scanner.

Speichert und laedt vergangene Scan-Konfigurationen aus
~/.console-error-scanner/history.json.
"""

from __future__ import annotations

import getpass
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """Einzelner Eintrag in der Scan-History.

    Speichert alle Parameter eines Scans, damit dieser
    spaeter wiederholt werden kann.

    Attributes:
        sitemap_url: URL der gescannten Sitemap.
        timestamp: Zeitstempel im ISO-Format.
        user: Benutzername zum Zeitpunkt des Scans.
        concurrency: Parallele Browser-Tabs.
        timeout: Timeout pro Seite in Sekunden.
        console_level: Console-Level (error/warn/all).
        url_filter: URL-Filter (Teilstring).
        user_agent: Custom User-Agent oder leer.
        cookies: Liste der Cookies als Dicts.
        whitelist_path: Pfad zur Whitelist-JSON oder leer.
        accept_consent: True=Consent akzeptieren, False=nur Banner verstecken.
    """

    sitemap_url: str
    timestamp: str = ""
    user: str = ""
    concurrency: int = 8
    timeout: int = 30
    console_level: str = "warn"
    url_filter: str = ""
    user_agent: str = ""
    cookies: list[dict[str, str]] = field(default_factory=list)
    whitelist_path: str = ""
    accept_consent: bool = True

    def to_dict(self) -> dict:
        """Konvertiert den Eintrag in ein Dictionary fuer JSON.

        Returns:
            Dictionary mit allen Feldern.
        """
        return {
            "sitemap_url": self.sitemap_url,
            "timestamp": self.timestamp,
            "user": self.user,
            "concurrency": self.concurrency,
            "timeout": self.timeout,
            "console_level": self.console_level,
            "url_filter": self.url_filter,
            "user_agent": self.user_agent,
            "cookies": self.cookies,
            "whitelist_path": self.whitelist_path,
            "accept_consent": self.accept_consent,
        }

    @staticmethod
    def from_dict(data: dict) -> HistoryEntry:
        """Erstellt einen HistoryEntry aus einem Dictionary.

        Args:
            data: Dictionary mit den Feldern des Eintrags.

        Returns:
            Neuer HistoryEntry.
        """
        return HistoryEntry(
            sitemap_url=data.get("sitemap_url", ""),
            timestamp=data.get("timestamp", ""),
            user=data.get("user", ""),
            concurrency=data.get("concurrency", 8),
            timeout=data.get("timeout", 30),
            console_level=data.get("console_level", "warn"),
            url_filter=data.get("url_filter", ""),
            user_agent=data.get("user_agent", ""),
            cookies=data.get("cookies", []),
            whitelist_path=data.get("whitelist_path", ""),
            accept_consent=data.get("accept_consent", True),
        )

    def display_label(self) -> str:
        """Erzeugt ein kompaktes Label fuer die Anzeige in der History-Liste.

        Format: "2026-02-13 14:30 | www.example.com | --cookie ... | --whitelist ..."

        Returns:
            Kurzform-String fuer die Listenanzeige.
        """
        # Datum kuerzen: nur YYYY-MM-DD HH:MM
        date_part = self.timestamp[:16].replace("T", " ") if self.timestamp else "?"

        # Hostname extrahieren
        try:
            host = urlparse(self.sitemap_url).hostname or self.sitemap_url
        except Exception:
            host = self.sitemap_url

        parts = [date_part, host]

        if self.cookies:
            cookie_names = ", ".join(c.get("name", "?") for c in self.cookies)
            parts.append(f"--cookie {cookie_names}")

        if self.whitelist_path:
            parts.append(f"--whitelist {self.whitelist_path}")

        if self.url_filter:
            parts.append(f"--filter {self.url_filter}")

        if self.user_agent:
            parts.append("--user-agent ...")

        if not self.accept_consent:
            parts.append("--no-consent")

        return " | ".join(parts)


class History:
    """Verwaltet die Scan-History in ~/.console-error-scanner/history.json.

    Stellt statische Methoden zum Laden, Speichern und Hinzufuegen
    von History-Eintraegen bereit.
    """

    HISTORY_DIR = Path.home() / ".console-error-scanner"
    HISTORY_FILE = HISTORY_DIR / "history.json"
    MAX_ENTRIES = 50

    @staticmethod
    def load() -> list[HistoryEntry]:
        """Laedt die History aus der JSON-Datei.

        Gibt eine leere Liste zurueck bei Fehler oder fehlender Datei.

        Returns:
            Liste der HistoryEntry-Objekte (neueste zuerst).
        """
        if not History.HISTORY_FILE.is_file():
            return []

        try:
            raw = History.HISTORY_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
            return [HistoryEntry.from_dict(item) for item in data]
        except Exception as exc:
            logger.warning("History konnte nicht geladen werden: %s", exc)
            return []

    @staticmethod
    def save(entries: list[HistoryEntry]) -> None:
        """Speichert die History in die JSON-Datei.

        Erstellt das Verzeichnis falls es nicht existiert.

        Args:
            entries: Liste der HistoryEntry-Objekte.
        """
        try:
            History.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            data = [entry.to_dict() for entry in entries]
            History.HISTORY_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("History konnte nicht gespeichert werden: %s", exc)

    @staticmethod
    def add(entry: HistoryEntry) -> None:
        """Fuegt einen neuen Eintrag an den Anfang der History hinzu.

        Laedt die aktuelle History, stellt den neuen Eintrag voran,
        kuerzt auf MAX_ENTRIES und speichert.

        Args:
            entry: Der neue HistoryEntry.
        """
        # Timestamp und User setzen falls nicht vorhanden
        if not entry.timestamp:
            entry.timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if not entry.user:
            try:
                entry.user = getpass.getuser()
            except Exception:
                entry.user = "unknown"

        entries = History.load()
        entries.insert(0, entry)

        # Auf Maximum kuerzen
        if len(entries) > History.MAX_ENTRIES:
            entries = entries[:History.MAX_ENTRIES]

        History.save(entries)
