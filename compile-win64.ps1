#Requires -Version 5.1
<#
.SYNOPSIS
    Compiles console-error-scanner into a standalone Windows binary with Nuitka.

.DESCRIPTION
    Self-contained --standalone build (no Python install needed on the target).
    Bundles the Playwright Chromium headless shell into
    dist\console-error-scanner\browsers\, so render mode works without a
    separate Playwright install. __main__.py points PLAYWRIGHT_BROWSERS_PATH at
    that folder when running as a compiled binary.

    Output: dist\console-error-scanner\ + dist\console-error-scanner-vX.Y.Z-windows-x64.zip
#>

$ErrorActionPreference = "Stop"

$root    = $PSScriptRoot
$entry   = Join-Path $root "src\console_error_scanner\__main__.py"
$initPy  = Join-Path $root "src\console_error_scanner\__init__.py"
$outDir  = Join-Path $root "dist"
$distDir = Join-Path $outDir "console-error-scanner"

# venv mit dem Lockfile abgleichen - VOR der python-Ermittlung, damit .venv
# auch bei einem frischen Checkout (z.B. CI) existiert.
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "Syncing venv (uv sync --inexact)..." -ForegroundColor Cyan
    & uv sync --inexact --project $root
    if ($LASTEXITCODE -ne 0) { throw "uv sync fehlgeschlagen" }
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

# Chromium pruefen/aktualisieren - 'playwright install' ist idempotent.
Write-Host "Checking Playwright Chromium..." -ForegroundColor Cyan
& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "playwright install fehlgeschlagen" }

$version = ([regex]'__version__\s*=\s*"([^"]+)"').Match((Get-Content -Raw $initPy)).Groups[1].Value
if (-not $version) { throw "Konnte __version__ nicht aus $initPy lesen" }

Write-Host "Compiling console-error-scanner v$version with Nuitka..." -ForegroundColor Cyan
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
$started = Get-Date

# Den Playwright-Node-Treiber NICHT explizit einschliessen - das macht Nuitkas
# eingebautes playwright-Plugin. Ein zusaetzliches --include-package-data=
# playwright kollidiert unter Linux mit dem Plugin ("data file
# 'playwright/driver/node' conflicts with exe").
& $python -m nuitka `
    --standalone `
    --assume-yes-for-downloads `
    --remove-output `
    --include-package=console_error_scanner `
    --include-package-data=console_error_scanner `
    --output-dir=$outDir `
    --output-filename=console-error-scanner.exe `
    --company-name="Michael Blaess" `
    --product-name="console-error-scanner" `
    --file-version=$version `
    --product-version=$version `
    $entry

if ($LASTEXITCODE -ne 0) { throw "Nuitka-Build fehlgeschlagen (Exit $LASTEXITCODE)" }

# Nuitka benennt den dist-Ordner nach dem Hauptmodul (__main__.dist) - umbenennen
$nuitkaDist = Join-Path $outDir "__main__.dist"
if (Test-Path $nuitkaDist) { Rename-Item -Path $nuitkaDist -NewName "console-error-scanner" }

# Nur die NEUESTE Headless-Shell kopieren (~265 MB). Alle Use-Cases laufen
# headless - das volle Chromium (~407 MB) wird nie gebraucht.
Write-Host "Bundling Chromium headless shell..." -ForegroundColor Cyan
$browsersDir = Join-Path $distDir "browsers"
New-Item -ItemType Directory -Path $browsersDir -Force | Out-Null
$cache = Join-Path $env:LOCALAPPDATA "ms-playwright"
$latest = Get-ChildItem -Path $cache -Directory -Filter "chromium_headless_shell-*" |
    Sort-Object { [int]($_.Name -replace '.*-', '') } -Descending |
    Select-Object -First 1
if (-not $latest) { throw "Kein chromium_headless_shell im Playwright-Cache gefunden" }
Copy-Item -Recurse -Force $latest.FullName (Join-Path $browsersDir $latest.Name)

$elapsed = [int]((Get-Date) - $started).TotalSeconds
$exe     = Join-Path $distDir "console-error-scanner.exe"
$sizeMB  = [math]::Round(((Get-ChildItem -Recurse $distDir | Measure-Object Length -Sum).Sum) / 1MB, 1)

$zip = Join-Path $outDir "console-error-scanner-v$version-windows-x64.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path $distDir -DestinationPath $zip
$zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)

Write-Host ""
Write-Host "Done in ${elapsed}s" -ForegroundColor Green
Write-Host "  dist folder : $distDir  (${sizeMB} MB)"
Write-Host "  zip         : $zip  (${zipMB} MB)"
Write-Host "  run         : $exe"
