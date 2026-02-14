@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  Console Error Scanner - Build
REM  Erstellt eine Standalone-EXE mit gebundeltem Chromium.
REM  Ergebnis: dist\console-error-scanner\
REM
REM  Voraussetzung: Python 3.10+ muss installiert sein.
REM  Optional: --skip-chromium (Chromium nicht kopieren)
REM ============================================================

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Console Error Scanner - Build              ║
echo  ╚══════════════════════════════════════════════╝
echo.

set SKIP_CHROMIUM=0
if "%1"=="--skip-chromium" set SKIP_CHROMIUM=1

REM --- Python pruefen ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Python wurde nicht gefunden!
    echo  Bitte Python 3.10+ installieren: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% gefunden

REM --- Build-Umgebung (.build-venv) ---
set BUILD_VENV=%~dp0.build-venv

if exist "%BUILD_VENV%\Scripts\python.exe" (
    echo  [OK] Build-Umgebung existiert bereits
) else (
    echo  Erstelle Build-Umgebung...
    python -m venv "%BUILD_VENV%"
    if errorlevel 1 (
        echo  [FEHLER] Konnte Build-Umgebung nicht erstellen!
        pause
        exit /b 1
    )
    echo  [OK] Build-Umgebung erstellt
)

set BPYTHON=%BUILD_VENV%\Scripts\python.exe
set BPIP=%BUILD_VENV%\Scripts\pip.exe

REM --- Abhaengigkeiten installieren ---
echo.
echo  Installiere Abhaengigkeiten...
"%BPIP%" install --upgrade pip --quiet 2>nul
"%BPIP%" install -e "%~dp0." --quiet
if errorlevel 1 (
    echo  [FEHLER] Paket-Installation fehlgeschlagen!
    pause
    exit /b 1
)
echo  [OK] Paket installiert

"%BPIP%" install pyinstaller --quiet
if errorlevel 1 (
    echo  [FEHLER] PyInstaller-Installation fehlgeschlagen!
    pause
    exit /b 1
)
echo  [OK] PyInstaller installiert

REM --- Playwright Chromium installieren (falls noetig) ---
echo.
echo  Stelle sicher dass Chromium installiert ist...
"%BUILD_VENV%\Scripts\playwright.exe" install chromium
if errorlevel 1 (
    echo  [FEHLER] Chromium-Installation fehlgeschlagen!
    pause
    exit /b 1
)
echo  [OK] Chromium verfuegbar

REM --- Alte Builds aufraeumen ---
if exist "%~dp0dist\console-error-scanner" (
    echo.
    echo  Raeume alten Build auf...
    rmdir /s /q "%~dp0dist\console-error-scanner"
)
if exist "%~dp0build" (
    rmdir /s /q "%~dp0build"
)

REM --- PyInstaller ausfuehren ---
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   PyInstaller laeuft...                      ║
echo  ╚══════════════════════════════════════════════╝
echo.

"%BPYTHON%" -m PyInstaller "%~dp0console-error-scanner.spec" --noconfirm
if errorlevel 1 (
    echo.
    echo  [FEHLER] PyInstaller Build fehlgeschlagen!
    pause
    exit /b 1
)
echo.
echo  [OK] PyInstaller Build erfolgreich

REM --- Chromium in dist kopieren ---
set DIST_DIR=%~dp0dist\console-error-scanner

if %SKIP_CHROMIUM%==1 (
    echo.
    echo  [SKIP] Chromium-Kopie uebersprungen (--skip-chromium)
    goto :after_chromium
)

echo.
echo  Kopiere Chromium-Browser...

REM Playwright-Browser-Pfad ermitteln
for /f "delims=" %%p in ('"%BPYTHON%" -c "import os; print(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright'))"') do set PW_BROWSERS=%%p

if not exist "%PW_BROWSERS%" (
    echo  [FEHLER] Playwright-Browser nicht gefunden unter: %PW_BROWSERS%
    pause
    exit /b 1
)

REM browsers-Ordner im dist erstellen
mkdir "%DIST_DIR%\browsers" 2>nul

REM Chromium-Ordner finden und kopieren (z.B. chromium-1208)
set CHROMIUM_FOUND=0
for /d %%d in ("%PW_BROWSERS%\chromium-*") do (
    echo  Kopiere %%~nxd ...
    xcopy /e /i /q /y "%%d" "%DIST_DIR%\browsers\%%~nxd" >nul
    set CHROMIUM_FOUND=1
)

if %CHROMIUM_FOUND%==0 (
    echo  [FEHLER] Kein Chromium-Ordner gefunden in %PW_BROWSERS%
    pause
    exit /b 1
)

echo  [OK] Chromium kopiert

:after_chromium

REM --- Whitelist + README beilegen ---
echo.
echo  Kopiere Zusatzdateien...
if exist "%~dp0whitelist.json" (
    copy /y "%~dp0whitelist.json" "%DIST_DIR%\whitelist.json" >nul
    echo  [OK] whitelist.json
)
if exist "%~dp0README.md" (
    copy /y "%~dp0README.md" "%DIST_DIR%\README.md" >nul
    echo  [OK] README.md
)

REM --- Starter-BAT erstellen ---
(
echo @echo off
echo REM Console Error Scanner - Starter
echo REM Verwendung: scan.bat SITEMAP_URL [OPTIONS]
echo.
echo "%%~dp0console-error-scanner.exe" %%*
) > "%DIST_DIR%\scan.bat"
echo  [OK] scan.bat

REM --- Groesse berechnen ---
echo.
set TOTAL_SIZE=0
for /f "tokens=3" %%s in ('dir /s "%DIST_DIR%" ^| findstr "Datei(en)"') do (
    set TOTAL_SIZE=%%s
)
echo  Ordnergroesse: %TOTAL_SIZE% Bytes

REM --- Fertig ---
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   Build abgeschlossen!                       ║
echo  ╠══════════════════════════════════════════════╣
echo  ║                                              ║
echo  ║   Ausgabe: dist\console-error-scanner\       ║
echo  ║                                              ║
echo  ║   Testen:                                    ║
echo  ║     cd dist\console-error-scanner            ║
echo  ║     scan.bat https://example.com/sitemap.xml ║
echo  ║                                              ║
echo  ║   Verteilen:                                 ║
echo  ║     Den Ordner zippen und weitergeben.       ║
echo  ║     Kein Python noetig!                      ║
echo  ║                                              ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
