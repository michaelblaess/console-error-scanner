#!/usr/bin/env bash
# Console Error Scanner - Startskript
# Verwendung: ./run.sh URL [OPTIONS]
#
# Nutzt die virtuelle Umgebung (.venv) falls vorhanden,
# sonst das globale Python.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ -x "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" -m console_error_scanner "$@"
else
    python3 -m console_error_scanner "$@"
fi
