"""Fusszeile: 'Scan abbrechen' erscheint nur waehrend eines Laufs.

Der Scanner konnte schon immer abbrechen (Scanner.cancel), aber die Bedienung
fehlte: ausgeloest wurde der Abbruch nur beim Beenden mit 'q' - und damit war
auch die Ergebnistabelle weg. Diese Tests halten die neue Taste fest.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from console_error_scanner import app as app_module
from console_error_scanner.app import ConsoleErrorScannerApp
from console_error_scanner.i18n import load_locale, t
from console_error_scanner.models import settings as settings_module
from console_error_scanner.models.settings import Settings


def _isolate(tmp_path: Path, monkeypatch: object) -> None:
    """Verlegt die settings.json in tmp_path und ueberspringt den Haftungshinweis."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "SETTINGS_DIR", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(Settings, "SETTINGS_DIR", tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(Settings, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(app_module, "SETTINGS_FILE", settings_file)  # type: ignore[attr-defined]
    monkeypatch.setattr(ConsoleErrorScannerApp, "_ask_disclaimer", lambda self: None)  # type: ignore[attr-defined]
    load_locale("de")


class FakeScanner:
    """Steht fuer einen laufenden Scan, ohne Browser und ohne Netz."""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


def _visible_actions(app: ConsoleErrorScannerApp) -> set[str]:
    """Aktionen, deren Taste tatsaechlich Platz in der Fusszeile belegt."""
    return {
        str(getattr(key, "action", ""))
        for key in app.query("FooterKey")
        if key.display and key.region.width > 0
    }


def test_cancel_key_appears_only_while_scanning(tmp_path: Path, monkeypatch: object) -> None:
    _isolate(tmp_path, monkeypatch)

    async def drive() -> tuple[set[str], set[str], bool, set[str]]:
        app = ConsoleErrorScannerApp()
        async with app.run_test(size=(200, 45)) as pilot:
            for _ in range(4):
                await pilot.pause()
            idle = _visible_actions(app)

            scanner = FakeScanner()
            app._scan_running = True
            app._scanner = scanner  # type: ignore[assignment]
            app.refresh_bindings()
            for _ in range(4):
                await pilot.pause()
            running = _visible_actions(app)

            await pilot.press("x")
            await pilot.pause()
            cancelled = scanner.cancelled

            app._scan_running = False
            app._scanner = None
            app.refresh_bindings()
            for _ in range(4):
                await pilot.pause()
            after = _visible_actions(app)
        return idle, running, cancelled, after

    idle, running, cancelled, after = asyncio.run(drive())

    assert "cancel_scan" not in idle, "Abbrechen steht im Fuss, obwohl nichts laeuft"
    assert "start_scan" in idle

    assert "cancel_scan" in running, "Abbrechen fehlt im Fuss, obwohl ein Lauf laeuft"
    assert "start_scan" not in running, "Crawl wird waehrend eines Laufs weiter angeboten"

    assert cancelled is True, "'x' hat den Abbruch nicht an den Scanner gemeldet"
    assert "cancel_scan" not in after
    assert "start_scan" in after


def test_cancel_without_scan_is_harmless(tmp_path: Path, monkeypatch: object) -> None:
    """Ohne Lauf darf die Aktion nichts kaputtmachen (etwa ueber die Befehlsliste)."""
    _isolate(tmp_path, monkeypatch)

    async def drive() -> None:
        app = ConsoleErrorScannerApp()
        async with app.run_test(size=(200, 45)) as pilot:
            await pilot.pause()
            app.action_cancel_scan()
            await pilot.pause()

    asyncio.run(drive())


def test_progress_timer_keeps_the_cancel_message(tmp_path: Path, monkeypatch: object) -> None:
    """Der Fortschritts-Timer darf die Abbruch-Meldung nicht ueberschreiben.

    Genau das machte den Abbruch fuer den Anwender unsichtbar: die Taste wirkte,
    aber eine halbe Sekunde spaeter stand wieder "Scanning 42%" im Kopf - es sah
    aus, als sei nichts passiert.
    """
    _isolate(tmp_path, monkeypatch)

    async def drive() -> tuple[str, str]:
        app = ConsoleErrorScannerApp()
        async with app.run_test(size=(200, 45)) as pilot:
            await pilot.pause()
            app._scan_total = 40
            app._scan_current = 12

            app._tick_scan_progress()  # normaler Lauf
            waehrend_des_laufs = str(app.sub_title)

            app._scan_cancelled = True
            app._tick_scan_progress()  # derselbe Timer nach dem Abbruch
            nach_dem_abbruch = str(app.sub_title)
        return waehrend_des_laufs, nach_dem_abbruch

    waehrend, nachher = asyncio.run(drive())

    assert "12" in waehrend, "der Fortschritt wird im normalen Lauf nicht mehr angezeigt"
    assert nachher == t("subtitle.cancelling"), (
        f"der Timer hat die Abbruch-Meldung ueberschrieben: {nachher!r}"
    )


def test_cancel_closes_open_contexts() -> None:
    """Der Abbruch kappt die laufenden Seiten, statt sie zu Ende laden zu lassen.

    Ohne das laeuft jede angefangene Seite komplett durch (Laden, Consent,
    Lazy-Load-Scroll) - der Lauf endet erst viele Sekunden spaeter, und in der
    Zwischenzeit sieht es aus, als haette die Taste nichts bewirkt.
    """
    from console_error_scanner.services.scanner import Scanner

    geschlossen: list[str] = []

    class FakeContext:
        def __init__(self, name: str) -> None:
            self.name = name

        async def close(self) -> None:
            geschlossen.append(self.name)

    async def drive() -> None:
        scanner = Scanner()
        scanner._open_contexts = {FakeContext("a"), FakeContext("b")}  # type: ignore[assignment]
        scanner.cancel()
        await asyncio.sleep(0)  # der Schliess-Task laeuft im Hintergrund
        await asyncio.sleep(0)

    asyncio.run(drive())

    assert sorted(geschlossen) == ["a", "b"], f"nicht alle Kontexte gekappt: {geschlossen}"


def test_scanner_starts_no_retry_after_cancel() -> None:
    """Ein abgebrochener Lauf darf nicht noch im Backoff (5/10/20 s) haengen."""
    from console_error_scanner.models.scan_result import ScanResult
    from console_error_scanner.services.scanner import Scanner

    scanner = Scanner()
    scanner.cancel()
    versuche = []

    async def nie_aufrufen(result: object, log: object) -> None:
        versuche.append(result)
        raise AssertionError("nach dem Abbruch darf kein Versuch mehr starten")

    scanner._do_scan_page = nie_aufrufen  # type: ignore[assignment]
    asyncio.run(scanner._scan_single_page(ScanResult(url="https://example.invalid/"), lambda _: None))

    assert not versuche
