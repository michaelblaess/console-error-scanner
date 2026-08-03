"""Gemeinsame Test-Vorbereitung.

**Kein Test darf in das echte Benutzerverzeichnis schreiben.** Die App legt
Einstellungen, Verlauf, Vorschau-Bilder und Absturzberichte unter
``~/.console-error-scanner`` ab. Ein Test, der die App hochfaehrt, wuerde sonst
die Daten des Anwenders veraendern - im sitemap-tracker ist genau das passiert
(Wegwerf-Laeufe im echten Crawl-Verlauf).

Das Umbiegen von ``USERPROFILE``/``HOME`` genuegt nicht: die Pfade stehen als
Modul- und Klassenkonstanten fest und werden beim Import einmal aus
``Path.home()`` berechnet. Sie muessen deshalb einzeln umgehaengt werden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from console_error_scanner import app as app_module
from console_error_scanner.models import settings as settings_module
from console_error_scanner.models.history import History
from console_error_scanner.models.settings import Settings
from console_error_scanner.services import preview_service as preview_module


@pytest.fixture(autouse=True)
def _isolated_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Verlegt alle Nutzerdateien in ein Wegwerf-Verzeichnis.

    Bewusst ueber ``tmp_path_factory`` und NICHT unter ``tmp_path``: Letzteres
    gehoert dem einzelnen Test, und mancher prueft, dass sein Verzeichnis leer
    bleibt.
    """
    home = tmp_path_factory.mktemp("home")

    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))

    monkeypatch.setattr(settings_module, "SETTINGS_DIR", home)
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", home / "settings.json")
    monkeypatch.setattr(Settings, "SETTINGS_DIR", home, raising=False)
    monkeypatch.setattr(Settings, "SETTINGS_FILE", home / "settings.json", raising=False)
    monkeypatch.setattr(app_module, "SETTINGS_FILE", home / "settings.json")
    monkeypatch.setattr(History, "HISTORY_DIR", home, raising=False)
    monkeypatch.setattr(History, "HISTORY_FILE", home / "history.json", raising=False)
    monkeypatch.setattr(preview_module, "CACHE_DIR", home / "preview-cache", raising=False)
    return home
