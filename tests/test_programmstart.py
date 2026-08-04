"""Startet das Programm wirklich - als Unterprozess, nicht per Import.

Der Import allein beweist gar nichts: bei ``import console_error_scanner.__main__``
ist ``__name__`` nicht ``"__main__"``, der Startblock am Dateiende feuert also
nie, und Python parst die Datei vollstaendig durch. Jeder Name ist danach
gebunden - auch einer, der zur echten Laufzeit noch gar nicht existiert.

Genau daran ist v1.14.0 vorbeigelaufen: der Startblock stand mitten in der
Datei, vor den Funktionen, die ``main()`` als Erstes aufruft. Die gesamte
Testsuite blieb gruen, waehrend ``python -m console_error_scanner`` mit einem
NameError abbrach. Nur ein echter Prozessstart kann diesen Fehler sehen.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PAKET = "console_error_scanner"


def test_programmstart_ueber_python_m() -> None:
    """``python -m <paket>`` muss sauber hochkommen.

    ``--help`` reicht als Probe: argparse laeuft erst, nachdem ``main()`` seine
    Startroutinen durch hat - genau die Stelle, an der ein falsch platzierter
    Startblock zuschlaegt.
    """
    ergebnis = _starten()
    assert ergebnis.returncode == 0, (
        f"Programmstart fehlgeschlagen (Exit {ergebnis.returncode}). "
        f"Fehlerausgabe: {ergebnis.stderr}"
    )


def test_sitzungsklammer_wird_geschlossen(tmp_path: Path) -> None:
    """Nach einem sauberen Lauf muss in fault.log eine Ende-Zeile stehen.

    Die Klammer ist die halbe Fehlerdiagnose: fehlt die Ende-Zeile, gilt der
    Lauf als hart abgeraeumt. Wurde ``_write_fault_end`` erst hinter dem
    Startblock definiert, verschluckte das ``contextlib.suppress`` im
    ``atexit.register`` den NameError - lautlos. Jeder saubere Lauf sah danach
    aus wie ein abgewuergter Prozess.

    Das Benutzerverzeichnis wird umgebogen, damit der Test weder die echte
    fault.log liest noch beschreibt.
    """
    umgebung = {k: v for k, v in os.environ.items() if k not in ("USERPROFILE", "HOME")}
    umgebung["USERPROFILE"] = str(tmp_path)
    umgebung["HOME"] = str(tmp_path)

    _starten(umgebung)

    treffer = list(tmp_path.rglob("fault.log"))
    assert treffer, "fault.log wurde nicht angelegt"
    inhalt = treffer[0].read_text(encoding="utf-8")
    assert "===== Start" in inhalt, inhalt
    assert "===== Ende" in inhalt, (
        f"Ende-Zeile fehlt - die Sitzungsklammer bleibt offen. Inhalt: {inhalt}"
    )


def _starten(umgebung: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Ruft das Paket als eigenen Prozess auf und liefert das Ergebnis."""
    return subprocess.run(
        [sys.executable, "-m", PAKET, "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        env=umgebung,
        timeout=120,
        check=False,
    )
