@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  Console Error Scanner - Setup
REM  Richtet eine virtuelle Umgebung ein und installiert alles.
REM  Voraussetzung: Python 3.10+ muss installiert sein.
REM ============================================================

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Console Error Scanner - Setup              ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM --- Python pruefen ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Python wurde nicht gefunden!
    echo  Bitte Python 3.10+ installieren: https://www.python.org/downloads/
    echo  WICHTIG: Bei der Installation "Add Python to PATH" ankreuzen!
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% gefunden
echo.

REM --- Virtuelle Umgebung erstellen ---
set VENV_DIR=%~dp0.venv

if exist "%VENV_DIR%\Scripts\python.exe" (
    echo  [OK] Virtuelle Umgebung existiert bereits
) else (
    echo  Erstelle virtuelle Umgebung...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  [FEHLER] Konnte virtuelle Umgebung nicht erstellen!
        pause
        exit /b 1
    )
    echo  [OK] Virtuelle Umgebung erstellt
)
echo.

REM --- pip upgrade ---
echo  Aktualisiere pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo  [OK] pip aktualisiert
echo.

REM --- Paket installieren ---
echo  Installiere Console Error Scanner + Abhaengigkeiten...
"%VENV_DIR%\Scripts\pip.exe" install -e "%~dp0." --quiet
if errorlevel 1 (
    echo  [FEHLER] Installation fehlgeschlagen!
    pause
    exit /b 1
)
echo  [OK] Console Error Scanner installiert
echo.

REM --- Playwright Chromium installieren ---
echo  Installiere Chromium Browser (kann 1-2 Minuten dauern)...
"%VENV_DIR%\Scripts\playwright.exe" install chromium
if errorlevel 1 (
    echo  [FEHLER] Chromium-Installation fehlgeschlagen!
    pause
    exit /b 1
)
echo  [OK] Chromium installiert
echo.

REM --- Fertig ---
echo  ╔══════════════════════════════════════════════╗
echo  ║   Setup abgeschlossen!                       ║
echo  ╠══════════════════════════════════════════════╣
echo  ║                                              ║
echo  ║   Starten mit:                               ║
echo  ║     run.bat SITEMAP_URL                      ║
echo  ║                                              ║
echo  ║   Beispiel:                                  ║
echo  ║     run.bat https://example.com/sitemap.xml  ║
echo  ║                                              ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
