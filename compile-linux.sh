#!/usr/bin/env bash
# compile-linux.sh - compiles console-error-scanner into a standalone Linux
# binary with Nuitka, with a bundled Chromium headless shell.
#
# Output: dist/console-error-scanner/console-error-scanner + browsers/, and
# dist/console-error-scanner-vX.Y.Z-linux-x86_64.tar.gz ready to hand out.
#
# Build machine needs: gcc, patchelf, Python headers
#   Debian/Ubuntu:  sudo apt install gcc patchelf python3-dev
# Target machine (to run bundled Chromium) needs Chromium's shared libs;
# on a fresh system: sudo playwright install-deps chromium

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
entry="$root/src/console_error_scanner/__main__.py"
init_py="$root/src/console_error_scanner/__init__.py"
out_dir="$root/dist"
dist_dir="$out_dir/console-error-scanner"

for tool in gcc patchelf; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Fehlt: $tool - bitte installieren (z.B. sudo apt install gcc patchelf python3-dev)" >&2
        exit 1
    fi
done

# venv mit dem Lockfile abgleichen - VOR der python-Ermittlung
if command -v uv >/dev/null 2>&1; then
    echo "Syncing venv (uv sync --inexact)..."
    uv sync --inexact --project "$root"
fi

if [ -x "$root/.venv/bin/python" ]; then
    python="$root/.venv/bin/python"
else
    python="python3"
fi

echo "Checking Playwright Chromium..."
"$python" -m playwright install chromium

# portables sed - 'grep -oP' gibt es auf dem BSD-grep von macOS nicht
version="$(sed -n 's/^__version__ *= *"\([^"]*\)".*/\1/p' "$init_py")"
if [ -z "$version" ]; then
    echo "Konnte __version__ nicht aus $init_py lesen" >&2
    exit 1
fi

echo "Compiling console-error-scanner v$version with Nuitka..."
rm -rf "$dist_dir"
started=$(date +%s)

# Den Playwright-Node-Treiber NICHT explizit einschliessen - das macht Nuitkas
# eingebautes playwright-Plugin. Ein zusaetzliches --include-package-data=
# playwright kollidiert hier mit dem Plugin ("data file
# 'playwright/driver/node' conflicts with exe").
"$python" -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --remove-output \
    --include-package=console_error_scanner \
    --include-package-data=console_error_scanner \
    --output-dir="$out_dir" \
    --output-filename=console-error-scanner \
    "$entry"

if [ -d "$out_dir/__main__.dist" ]; then
    mv "$out_dir/__main__.dist" "$dist_dir"
fi

# Nur die neueste Headless-Shell mitbuendeln (~265 MB). Alle Use-Cases laufen
# headless - das volle Chromium (~407 MB) wird nie gebraucht.
echo "Bundling Chromium headless shell..."
browsers_dir="$dist_dir/browsers"
mkdir -p "$browsers_dir"
cache="${HOME}/.cache/ms-playwright"
latest="$(ls -d "$cache/chromium_headless_shell-"* 2>/dev/null | sort -V | tail -1)"
if [ ! -d "$latest" ]; then
    echo "Kein chromium_headless_shell im Playwright-Cache gefunden" >&2
    exit 1
fi
cp -r "$latest" "$browsers_dir/"

elapsed=$(( $(date +%s) - started ))
size_mb=$(du -sm "$dist_dir" | cut -f1)

tarball="$out_dir/console-error-scanner-v$version-linux-x86_64.tar.gz"
rm -f "$tarball"
tar -czf "$tarball" -C "$out_dir" console-error-scanner
tar_mb=$(du -sm "$tarball" | cut -f1)

echo ""
echo "Done in ${elapsed}s"
echo "  dist folder : $dist_dir  (${size_mb} MB)"
echo "  tarball     : $tarball  (${tar_mb} MB)"
