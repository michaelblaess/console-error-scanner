#!/usr/bin/env bash
# ============================================================
#  Console Error Scanner - Setup
#  Richtet eine virtuelle Umgebung ein und installiert alles.
#  Voraussetzung: Python 3.10+ muss installiert sein.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Console Error Scanner - Setup              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo

# --- Python pruefen ---
if ! command -v python3 &> /dev/null; then
    echo "  [FEHLER] Python wurde nicht gefunden!"
    echo "  Bitte Python 3.10+ installieren."
    exit 1
fi

PYVER=$(python3 --version 2>&1)
echo "  [OK] $PYVER gefunden"
echo

# --- Virtuelle Umgebung erstellen ---
if [ -x "$VENV_DIR/bin/python" ]; then
    echo "  [OK] Virtuelle Umgebung existiert bereits"
else
    echo "  Erstelle virtuelle Umgebung..."
    python3 -m venv "$VENV_DIR"
    echo "  [OK] Virtuelle Umgebung erstellt"
fi
echo

# --- pip upgrade ---
echo "  Aktualisiere pip..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet
echo "  [OK] pip aktualisiert"
echo

# --- Paket installieren ---
echo "  Installiere Console Error Scanner + Abhaengigkeiten..."
"$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR" --quiet
echo "  [OK] Console Error Scanner installiert"
echo

# --- Playwright Chromium installieren ---
echo "  Installiere Chromium Browser (kann 1-2 Minuten dauern)..."
"$VENV_DIR/bin/playwright" install chromium
echo "  [OK] Chromium installiert"
echo

# --- Fertig ---
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Setup abgeschlossen!                       ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║                                              ║"
echo "  ║   Starten mit:                               ║"
echo "  ║     ./run.sh URL                             ║"
echo "  ║                                              ║"
echo "  ║   Beispiel:                                  ║"
echo "  ║     ./run.sh https://example.com             ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo
