# Console Error Scanner - Startskript
# Verwendung: .\run.ps1 SITEMAP_URL [OPTIONS]
#
# Nutzt die virtuelle Umgebung (.venv) falls vorhanden,
# sonst das globale Python.

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    & $venvPython -m console_error_scanner @args
} else {
    python -m console_error_scanner @args
}
