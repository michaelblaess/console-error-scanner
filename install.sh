#!/usr/bin/env bash
# ============================================================
#  Console Error Scanner - Installer
#
#  Verwendung:
#    curl -fsSL https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.sh | bash
#
#  Laedt das neueste Release von GitHub herunter und installiert es.
#  Keine Abhaengigkeiten noetig (kein Python, kein Git, kein Chrome).
#
#  Installiert nach: ~/.console-error-scanner/
#  Erstellt Wrapper:  ~/.local/bin/console-error-scanner
# ============================================================

set -e

REPO="michaelblaess/console-error-scanner"
INSTALL_DIR="$HOME/.console-error-scanner"
BIN_DIR="$HOME/.local/bin"
WRAPPER="$BIN_DIR/console-error-scanner"

echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Console Error Scanner - Installer          ║"
echo "  ╚══════════════════════════════════════════════╝"
echo

# --- OS und Architektur erkennen ---
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Linux*)  PLATFORM="linux" ;;
    Darwin*) PLATFORM="macos" ;;
    *)
        echo "  [FEHLER] Nicht unterstuetztes OS: $OS"
        echo "  Unterstuetzt: Linux, macOS"
        echo "  Fuer Windows: irm ...install.ps1 | iex"
        exit 1
        ;;
esac

case "$ARCH" in
    x86_64|amd64)    ARCH_SUFFIX="x64" ;;
    aarch64|arm64)   ARCH_SUFFIX="arm64" ;;
    *)
        echo "  [FEHLER] Nicht unterstuetzte Architektur: $ARCH"
        exit 1
        ;;
esac

# Artifact-Name bestimmen
ARTIFACT="console-error-scanner-${PLATFORM}-${ARCH_SUFFIX}"
ARCHIVE="${ARTIFACT}.tar.gz"

echo "  Plattform: $PLATFORM ($ARCH_SUFFIX)"
echo

# --- curl oder wget pruefen ---
DOWNLOAD_CMD=""
if command -v curl &> /dev/null; then
    DOWNLOAD_CMD="curl"
elif command -v wget &> /dev/null; then
    DOWNLOAD_CMD="wget"
else
    echo "  [FEHLER] Weder curl noch wget gefunden!"
    echo "  Bitte installieren: sudo apt install curl"
    exit 1
fi

# --- Neuestes Release von GitHub ermitteln ---
echo "  Suche neuestes Release..."
API_URL="https://api.github.com/repos/${REPO}/releases/latest"

if [ "$DOWNLOAD_CMD" = "curl" ]; then
    RELEASE_JSON=$(curl -fsSL "$API_URL" 2>/dev/null) || {
        echo "  [FEHLER] Konnte GitHub API nicht erreichen."
        echo "  Pruefe deine Internetverbindung."
        exit 1
    }
else
    RELEASE_JSON=$(wget -qO- "$API_URL" 2>/dev/null) || {
        echo "  [FEHLER] Konnte GitHub API nicht erreichen."
        exit 1
    }
fi

# Download-URL aus JSON extrahieren (ohne jq)
DOWNLOAD_URL=$(echo "$RELEASE_JSON" | grep -o "\"browser_download_url\": *\"[^\"]*${ARCHIVE}\"" | grep -o "https://[^\"]*")

if [ -z "$DOWNLOAD_URL" ]; then
    echo "  [FEHLER] Kein Release fuer ${ARCHIVE} gefunden!"
    echo
    echo "  Verfuegbare Assets:"
    echo "$RELEASE_JSON" | grep -o '"browser_download_url": *"[^"]*"' | sed 's/.*: *"/    /' | sed 's/"//'
    echo
    echo "  Moeglicherweise gibt es noch kein Release fuer deine Plattform."
    exit 1
fi

# Version extrahieren
VERSION=$(echo "$RELEASE_JSON" | grep -o '"tag_name": *"[^"]*"' | head -1 | sed 's/.*: *"//' | sed 's/"//')
echo "  [OK] Release gefunden: $VERSION"
echo

# --- Download ---
TMPDIR=$(mktemp -d)
TMPFILE="$TMPDIR/$ARCHIVE"

echo "  Lade herunter: $ARCHIVE"
if [ "$DOWNLOAD_CMD" = "curl" ]; then
    curl -fSL --progress-bar -o "$TMPFILE" "$DOWNLOAD_URL"
else
    wget --show-progress -qO "$TMPFILE" "$DOWNLOAD_URL"
fi
echo "  [OK] Download abgeschlossen"
echo

# --- Entpacken ---
echo "  Entpacke nach: $INSTALL_DIR"

# Alte Installation sichern
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR.bak"
    mv "$INSTALL_DIR" "$INSTALL_DIR.bak"
fi

mkdir -p "$INSTALL_DIR"
tar -xzf "$TMPFILE" -C "$INSTALL_DIR" --strip-components=1
rm -rf "$TMPDIR"

# Alte Sicherung entfernen
rm -rf "$INSTALL_DIR.bak"

echo "  [OK] Entpackt"
echo

# --- Wrapper-Script erstellen ---
mkdir -p "$BIN_DIR"

cat > "$WRAPPER" << 'SCRIPT'
#!/usr/bin/env bash
# Console Error Scanner - Wrapper (automatisch generiert)
SCANNER_DIR="$HOME/.console-error-scanner"
# PLAYWRIGHT_BROWSERS_PATH setzen fuer gebundeltes Chromium
if [ -d "$SCANNER_DIR/browsers" ]; then
    export PLAYWRIGHT_BROWSERS_PATH="$SCANNER_DIR/browsers"
fi
"$SCANNER_DIR/console-error-scanner" "$@"
SCRIPT
chmod +x "$WRAPPER"
chmod +x "$INSTALL_DIR/console-error-scanner"
echo "  [OK] Wrapper erstellt: $WRAPPER"

# --- PATH pruefen ---
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
    echo
    echo "  [HINWEIS] $BIN_DIR ist nicht im PATH."
    echo
    SHELL_NAME=$(basename "$SHELL" 2>/dev/null || echo "bash")
    case "$SHELL_NAME" in
        zsh)  RC_FILE="~/.zshrc" ;;
        fish) RC_FILE="~/.config/fish/config.fish" ;;
        *)    RC_FILE="~/.bashrc" ;;
    esac
    echo "  Fuege diese Zeile zu $RC_FILE hinzu:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
    echo "  Oder fuer diese Session:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# --- Fertig ---
echo
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   Installation abgeschlossen! ($VERSION)"
echo "  ╠══════════════════════════════════════════════╣"
echo "  ║                                              ║"
echo "  ║   Starten mit:                               ║"
echo "  ║     console-error-scanner URL                ║"
echo "  ║                                              ║"
echo "  ║   Beispiel:                                  ║"
echo "  ║     console-error-scanner https://example.com║"
echo "  ║                                              ║"
echo "  ║   Aktualisieren:                             ║"
echo "  ║     Installer erneut ausfuehren.             ║"
echo "  ║                                              ║"
echo "  ║   Deinstallieren:                            ║"
echo "  ║     rm -rf ~/.console-error-scanner          ║"
echo "  ║     rm ~/.local/bin/console-error-scanner    ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo
