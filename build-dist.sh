#!/usr/bin/env bash
# ============================================================
#  Console Error Scanner - Build
#  Erstellt eine Standalone-Distribution mit gebundeltem Chromium.
#  Ergebnis: dist/console-error-scanner/
#
#  Voraussetzung: Python 3.10+ muss installiert sein.
#  Optional: --skip-chromium (Chromium nicht kopieren)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_VENV="$SCRIPT_DIR/.build-venv"
DIST_DIR="$SCRIPT_DIR/dist/console-error-scanner"
SKIP_CHROMIUM=0

if [ "$1" = "--skip-chromium" ]; then
    SKIP_CHROMIUM=1
fi

echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Console Error Scanner - Build              ║"
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

# --- Build-Umgebung (.build-venv) ---
if [ -x "$BUILD_VENV/bin/python" ]; then
    echo "  [OK] Build-Umgebung existiert bereits"
else
    echo "  Erstelle Build-Umgebung..."
    python3 -m venv "$BUILD_VENV"
    echo "  [OK] Build-Umgebung erstellt"
fi

BPYTHON="$BUILD_VENV/bin/python"
BPIP="$BUILD_VENV/bin/pip"

# --- Abhaengigkeiten installieren ---
echo
echo "  Installiere Abhaengigkeiten..."
"$BPIP" install --upgrade pip --quiet 2>/dev/null
"$BPIP" install -e "$SCRIPT_DIR" --quiet
echo "  [OK] Paket installiert"

"$BPIP" install pyinstaller --quiet
echo "  [OK] PyInstaller installiert"

# --- Playwright Chromium installieren ---
echo
echo "  Stelle sicher dass Chromium installiert ist..."
"$BUILD_VENV/bin/playwright" install chromium
echo "  [OK] Chromium verfuegbar"

# --- Alte Builds aufraeumen ---
if [ -d "$DIST_DIR" ]; then
    echo
    echo "  Raeume alten Build auf..."
    rm -rf "$DIST_DIR"
fi
rm -rf "$SCRIPT_DIR/build"

# --- PyInstaller ausfuehren ---
echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   PyInstaller laeuft...                      ║"
echo "  ╚══════════════════════════════════════════════╝"
echo

"$BPYTHON" -m PyInstaller "$SCRIPT_DIR/console-error-scanner.spec" --noconfirm
echo
echo "  [OK] PyInstaller Build erfolgreich"

# --- Chromium in dist kopieren ---
if [ $SKIP_CHROMIUM -eq 1 ]; then
    echo
    echo "  [SKIP] Chromium-Kopie uebersprungen (--skip-chromium)"
else
    echo
    echo "  Kopiere Chromium-Browser..."

    # Playwright-Browser-Pfad ermitteln (Linux/macOS)
    PW_BROWSERS="$HOME/.cache/ms-playwright"
    if [ "$(uname)" = "Darwin" ]; then
        PW_BROWSERS="$HOME/Library/Caches/ms-playwright"
    fi

    if [ ! -d "$PW_BROWSERS" ]; then
        echo "  [FEHLER] Playwright-Browser nicht gefunden unter: $PW_BROWSERS"
        exit 1
    fi

    mkdir -p "$DIST_DIR/browsers"

    CHROMIUM_FOUND=0
    for chromium_dir in "$PW_BROWSERS"/chromium-*; do
        if [ -d "$chromium_dir" ]; then
            dir_name=$(basename "$chromium_dir")
            echo "  Kopiere $dir_name ..."
            cp -r "$chromium_dir" "$DIST_DIR/browsers/$dir_name"
            CHROMIUM_FOUND=1
        fi
    done

    if [ $CHROMIUM_FOUND -eq 0 ]; then
        echo "  [FEHLER] Kein Chromium-Ordner gefunden in $PW_BROWSERS"
        exit 1
    fi

    echo "  [OK] Chromium kopiert"
fi

# --- Whitelist + README beilegen ---
echo
echo "  Kopiere Zusatzdateien..."
[ -f "$SCRIPT_DIR/whitelist.json" ] && cp "$SCRIPT_DIR/whitelist.json" "$DIST_DIR/" && echo "  [OK] whitelist.json"
[ -f "$SCRIPT_DIR/README.md" ] && cp "$SCRIPT_DIR/README.md" "$DIST_DIR/" && echo "  [OK] README.md"

# --- Starter-Script erstellen ---
cat > "$DIST_DIR/scan.sh" << 'STARTER'
#!/usr/bin/env bash
# Console Error Scanner - Starter
# Verwendung: ./scan.sh URL [OPTIONS]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/console-error-scanner" "$@"
STARTER
chmod +x "$DIST_DIR/scan.sh"
echo "  [OK] scan.sh"

# --- Groesse berechnen ---
echo
TOTAL_SIZE=$(du -sh "$DIST_DIR" | cut -f1)
echo "  Ordnergroesse: $TOTAL_SIZE"

# --- Fertig ---
echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Build abgeschlossen!                       ║"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║                                              ║"
echo "  ║   Ausgabe: dist/console-error-scanner/       ║"
echo "  ║                                              ║"
echo "  ║   Testen:                                    ║"
echo "  ║     cd dist/console-error-scanner            ║"
echo "  ║     ./scan.sh https://example.com            ║"
echo "  ║                                              ║"
echo "  ║   Verteilen:                                 ║"
echo "  ║     Den Ordner zippen und weitergeben.       ║"
echo "  ║     Kein Python noetig!                      ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo
