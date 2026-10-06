"""Der Report nennt die Dauer des Scans, nicht die Zeit bis zum Speichern.

Vorher rechnete die Taste 'r' die Dauer erst beim Speichern aus: Scan-Start bis
Tastendruck. Wer den Report eine Minute nach dem Scan speicherte, bekam eine
Minute mehr "Scan-Dauer". Diese Tests halten fest, dass die Dauer am Ende des
Laufs eingefroren wird.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from console_error_scanner import app as app_module
from console_error_scanner.app import ConsoleErrorScannerApp
from console_error_scanner.i18n import load_locale
from console_error_scanner.models import settings as settings_module
from console_error_scanner.models.scan_result import PageStatus, ScanResult, ScanSummary
from console_error_scanner.models.settings import Settings
from console_error_scanner.services.reporter import Reporter


def _isolate(tmp_path: Path, monkeypatch: object) -> None:
    """Verlegt die settings.json in tmp_path und ueberspringt den Haftungshinweis."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "SETTINGS_DIR", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(Settings, "SETTINGS_DIR", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(Settings, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(app_module, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(ConsoleErrorScannerApp, "_ask_disclaimer", lambda self: None)  # type: ignore[attr-defined]
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    load_locale("de")


def _capture_summaries(monkeypatch: object) -> list[ScanSummary]:
    """Faengt ab, was an den Reporter geht, ohne Dateien zu schreiben."""
    captured: list[ScanSummary] = []

    def fake_save(results: object, summary: ScanSummary, output_path: str, **_kwargs: object) -> str:
        captured.append(summary)
        return output_path

    monkeypatch.setattr(Reporter, "save_json", staticmethod(fake_save))  # type: ignore[attr-defined]
    monkeypatch.setattr(Reporter, "save_html", staticmethod(fake_save))  # type: ignore[attr-defined]
    return captured


def test_report_duration_is_frozen_at_scan_end(tmp_path: Path, monkeypatch: object) -> None:
    _isolate(tmp_path, monkeypatch)
    captured = _capture_summaries(monkeypatch)

    async def drive() -> None:
        app = ConsoleErrorScannerApp(sitemap_url="https://example.com")
        async with app.run_test(size=(200, 45)) as pilot:
            await pilot.pause()
            app._results = [ScanResult(url="https://example.com/", status=PageStatus.OK)]
            # Der Scan lief 30 Sekunden. Die Uhr selbst bleibt unangetastet, Textual
            # und asyncio brauchen sie, verschoben wird nur der Startzeitpunkt.
            app._scan_start_time = time.monotonic() - 30.0
            app._freeze_scan_duration()
            # Danach wird 45 Sekunden lang gelesen: fuer die alte Rechnung dasselbe
            # wie ein um 45 Sekunden frueherer Start.
            app._scan_start_time -= 45.0
            app.action_save_reports()
            await pilot.pause()

    asyncio.run(drive())

    assert captured, "Der Report wurde nicht gespeichert"
    for summary in captured:
        assert 30_000 <= summary.scan_duration_ms < 32_000, (
            f"Report nennt {summary.scan_duration_ms} ms, der Scan lief 30000 ms"
        )


def test_new_scan_discards_old_duration(tmp_path: Path, monkeypatch: object) -> None:
    """Ein neuer Lauf darf nicht die Dauer des alten weitertragen."""
    _isolate(tmp_path, monkeypatch)

    async def drive() -> tuple[int, int]:
        app = ConsoleErrorScannerApp()
        async with app.run_test(size=(200, 45)) as pilot:
            await pilot.pause()
            app._scan_start_time = time.monotonic() - 12.0
            app._freeze_scan_duration()
            first = app._scan_duration_ms
            app._scan_start_time = time.monotonic() - 3.0
            app._freeze_scan_duration()
            return first, app._scan_duration_ms

    first, second = asyncio.run(drive())

    assert 12_000 <= first < 14_000
    assert 3_000 <= second < 5_000
