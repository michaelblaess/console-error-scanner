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
# Settings-Files aelterer Versionen koennen alte Slugs gespeichert haben -
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
    "gulf-racing": "textual-dark",
}


SETTINGS_DIR = Path.home() / ".console-error-scanner"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


@dataclass
class Settings:
    """Persistierte Benutzereinstellungen.

    Attributes:
        theme:
            Name des Textual-Themes.
        language:
            UI-Sprache (de/en).
        accept_consent:
            Consent-Akzeptierung aktiv.
        trigger_lazy_load:
            Seite scrollen fuer Lazy-Loading.
        concurrency:
            Parallele Browser-Tabs.
        timeout:
            Timeout pro Seite in Sekunden.
        console_level:
            Console-Level (error/warn/all).
        user_agent:
            Custom User-Agent.
        cookies:
            Roh-Cookies-String "name=value; name2=value2".
        whitelist_path:
            Pfad zur whitelist.json (leer = keine Whitelist).
    """

    theme: str = "textual-dark"
    language: str = "de"
    accept_consent: bool = True
    trigger_lazy_load: bool = True
    concurrency: int = 8
    timeout: int = 60
    console_level: str = "warn"
    user_agent: str = ""
    cookies: str = ""
    whitelist_path: str = ""
    no_headless: bool = False
    show_preview: bool = False

    SETTINGS_DIR = SETTINGS_DIR
    SETTINGS_FILE = SETTINGS_FILE

    def to_dict(self) -> dict:
        """Konvertiert die Einstellungen in ein Dictionary fuer JSON."""
        return {
            "theme": self.theme,
            "language": self.language,
            "accept_consent": self.accept_consent,
            "trigger_lazy_load": self.trigger_lazy_load,
            "concurrency": self.concurrency,
            "timeout": self.timeout,
            "console_level": self.console_level,
            "user_agent": self.user_agent,
            "cookies": self.cookies,
            "whitelist_path": self.whitelist_path,
            "no_headless": self.no_headless,
            "show_preview": self.show_preview,
        }

    @staticmethod
    def load() -> Settings:
        """Laedt die Einstellungen aus der JSON-Datei.

        Gibt Default-Einstellungen zurueck bei Fehler oder fehlender Datei.
        Migriert dabei alte Theme-Slugs aus textual-themes < 0.5 auf
        ihre aktuellen Namen und persistiert die Migration.
        """
        if not SETTINGS_FILE.is_file():
            return Settings()

        try:
            raw = SETTINGS_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return Settings()
            settings = Settings(
                theme=data.get("theme", "textual-dark"),
                language=data.get("language", "de"),
                accept_consent=data.get("accept_consent", True),
                trigger_lazy_load=data.get("trigger_lazy_load", True),
                concurrency=int(data.get("concurrency", 8)),
                timeout=int(data.get("timeout", 60)),
                console_level=str(data.get("console_level", "warn")),
                user_agent=str(data.get("user_agent", "")),
                cookies=str(data.get("cookies", "")),
                whitelist_path=str(data.get("whitelist_path", "")),
                no_headless=bool(data.get("no_headless", False)),
                show_preview=bool(data.get("show_preview", False)),
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
        """Speichert die Einstellungen in die JSON-Datei."""
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Settings konnten nicht gespeichert werden: %s", exc)


def parse_cookies(raw: str) -> list[dict[str, str]]:
    """Parst einen Cookie-String 'name=value; name2=value2' zu einer Liste.

    Args:
        raw: Cookie-String (Trenner: ';' oder ','; Whitespace tolerant).

    Returns:
        Liste von {"name": ..., "value": ...}-Dicts. Eintraege ohne '='
        werden uebersprungen.
    """
    if not raw or not raw.strip():
        return []
    parts: list[str] = []
    for chunk in raw.split(";"):
        parts.extend(p.strip() for p in chunk.split(",") if p.strip())
    cookies: list[dict[str, str]] = []
    for entry in parts:
        if "=" not in entry:
            continue
        name, value = entry.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name:
            cookies.append({"name": name, "value": value})
    return cookies


def cookies_to_string(cookies: list[dict[str, str]]) -> str:
    """Wandelt eine Cookie-Liste zurueck in den persistierbaren String.

    Args:
        cookies: Liste von {"name": ..., "value": ...}-Dicts.

    Returns:
        String der Form 'name=value; name2=value2'.
    """
    return "; ".join(f"{c.get('name', '').strip()}={c.get('value', '').strip()}" for c in cookies if c.get("name"))
