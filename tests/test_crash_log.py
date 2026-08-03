"""Ein Absturz muss auf Platte landen, nicht nur im Fehlerdialog.

Faellt der Dialog beim Neuaufbau selbst mit, geht der Bericht sonst verloren -
und unter Windows bleibt nur Steuerzeichen-Muell im Terminal zurueck.
"""

from __future__ import annotations

from pathlib import Path

from console_error_scanner import __version__
from console_error_scanner.app import ConsoleErrorScannerApp
from console_error_scanner.models import settings as settings_module
from console_error_scanner.models.settings import CRASH_LOG_NAME


def _crash_file() -> Path:
    return Path(settings_module.SETTINGS_FILE).parent / CRASH_LOG_NAME


def test_traceback_is_written_to_disk() -> None:
    app = ConsoleErrorScannerApp()
    try:
        raise RuntimeError("kaputt zum Testen")
    except RuntimeError as error:
        app._persist_crash(error)

    inhalt = _crash_file().read_text(encoding="utf-8")
    assert "kaputt zum Testen" in inhalt
    assert "RuntimeError" in inhalt
    assert __version__ in inhalt, "ohne Version laesst sich der Bericht nicht zuordnen"
    assert "Traceback" in inhalt


def test_reports_are_appended() -> None:
    """Ein zweiter Absturz darf den ersten nicht ueberschreiben."""
    app = ConsoleErrorScannerApp()
    for text in ("erster Fehler", "zweiter Fehler"):
        try:
            raise ValueError(text)
        except ValueError as error:
            app._persist_crash(error)

    inhalt = _crash_file().read_text(encoding="utf-8")
    assert "erster Fehler" in inhalt
    assert "zweiter Fehler" in inhalt


def test_fault_log_start_line() -> None:
    """faulthandler faengt ab, was unterhalb von Pythons Exception-Handling liegt."""
    import faulthandler

    from console_error_scanner.__main__ import _enable_faulthandler

    _enable_faulthandler()
    datei = Path(settings_module.SETTINGS_FILE).parent / "fault.log"
    assert datei.is_file(), "fault.log wurde nicht angelegt"
    erste_zeile = datei.read_text(encoding="utf-8").strip().split("\n")[0]
    # Die Startzeile belegt, dass der Prozess lief - fehlt danach alles Weitere,
    # wurde er von aussen abgeraeumt statt an einem Python-Fehler zu sterben.
    assert erste_zeile.startswith("===== Start ")
    assert __version__ in erste_zeile
    assert faulthandler.is_enabled()
