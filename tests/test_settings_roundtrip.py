"""Regression: Scanner-Einstellungen ueberleben Speichern + erneutes Oeffnen.

Deckt den Bug ab, bei dem 'robots.txt beachten' und 'Aufrufe drosseln' nach dem
Speichern wieder angehakt waren: die App reichte diese Felder weder in den Dialog
hinein (action_show_settings) noch aus dem Ergebnis zurueck in die persistierten
Einstellungen (_on_settings_closed). Der reine to_dict()-Roundtrip in
test_safe_defaults deckte das NICHT ab, weil er das App-Mapping ueberspringt.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Checkbox

from console_error_scanner import app as app_module
from console_error_scanner.app import ConsoleErrorScannerApp
from console_error_scanner.i18n import load_locale
from console_error_scanner.models import settings as settings_module
from console_error_scanner.models.settings import Settings


def _isolate(tmp_path: Path, monkeypatch: object) -> Path:
    """Verlegt die settings.json in tmp_path und ueberspringt den Disclaimer."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "SETTINGS_DIR", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(Settings, "SETTINGS_DIR", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(Settings, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(app_module, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(ConsoleErrorScannerApp, "_ask_disclaimer", lambda self: None)  # type: ignore[attr-defined]
    load_locale("de")
    return settings_file


def test_robots_and_rate_survive_save_and_reopen(tmp_path: Path, monkeypatch: object) -> None:
    _isolate(tmp_path, monkeypatch)

    async def drive() -> None:
        app = ConsoleErrorScannerApp()
        async with app.run_test() as pilot:
            app.action_show_settings()
            await pilot.pause()
            app.screen.query_one("#set-robots", Checkbox).value = False
            app.screen.query_one("#set-rate-on", Checkbox).value = False
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()

            # Erneut oeffnen: der Dialog muss den gespeicherten Zustand zeigen
            # (deckt das fehlende Feld im current-Dict ab).
            app.action_show_settings()
            await pilot.pause()
            assert app.screen.query_one("#set-robots", Checkbox).value is False
            assert app.screen.query_one("#set-rate-on", Checkbox).value is False

    asyncio.run(drive())

    # Und auf der Platte gelandet (deckt das fehlende Mapping in
    # _on_settings_closed ab).
    reloaded = Settings.load()
    assert reloaded.respect_robots is False
    assert reloaded.rate_limit_enabled is False
