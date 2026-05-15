# Console Error Scanner

<p align="center">
  <img src="docs/flags/gb.svg" height="13" alt=""> <a href="README.md">English</a> ·
  <img src="docs/flags/de.svg" height="13" alt=""> <b>Deutsch</b>
</p>

---

[![Stars](https://img.shields.io/github/stars/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=fbbf24)](https://github.com/michaelblaess/console-error-scanner/stargazers)
[![Forks](https://img.shields.io/github/forks/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=34d399)](https://github.com/michaelblaess/console-error-scanner/network/members)
[![Issues](https://img.shields.io/github/issues/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=f87171)](https://github.com/michaelblaess/console-error-scanner/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=a78bfa)](https://github.com/michaelblaess/console-error-scanner/pulls)

[![Last Commit](https://img.shields.io/github/last-commit/michaelblaess/console-error-scanner?logo=git&logoColor=white&color=3b82f6)](https://github.com/michaelblaess/console-error-scanner/commits/main)
[![License](https://img.shields.io/badge/license-Apache_2.0-3b82f6)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3b82f6?logo=python&logoColor=white)](https://www.python.org/)

TUI-Tool zum automatischen Scannen von Websites auf JavaScript Console-Errors und HTTP-Fehler (404, 5xx).
Eingabe ist eine Website-URL oder Sitemap-URL (XML). Bei Domain-URLs wird die Sitemap automatisch über robots.txt und typische Pfade gefunden. Ergebnisse werden live in einer Terminal-UI angezeigt und können als HTML- und JSON-Reports exportiert werden.

## Screenshots

### Hauptansicht
![Hauptansicht](docs/screenshots/01-main.png)

### Top 10 Fehler
![Top 10 Fehler](docs/screenshots/02-top-10-errors.png)

### Scan-History
![Scan-History](docs/screenshots/03-history.png)

## Installation

Keine Abhängigkeiten nötig - kein Python, kein Git, kein Chrome.

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.ps1 | iex
```

Danach ein neues Terminal öffnen und loslegen:

```bash
console-error-scanner https://www.example.com
```

### Aktualisieren

Einfach den Installer erneut ausführen - erkennt vorhandene Installation und überschreibt.

### Deinstallieren

```bash
# Linux/macOS
rm -rf ~/.console-error-scanner ~/.local/bin/console-error-scanner

# Windows PowerShell
Remove-Item -Recurse "$env:LOCALAPPDATA\console-error-scanner"
```

### Installationspfade

| OS | Programm | Wrapper / PATH |
|----|----------|----------------|
| Linux | `~/.console-error-scanner/` | `~/.local/bin/console-error-scanner` |
| macOS | `~/.console-error-scanner/` | `~/.local/bin/console-error-scanner` |
| Windows | `%LOCALAPPDATA%\console-error-scanner\` | `...\bin\console-error-scanner.cmd` (automatisch im PATH) |

## Verwendung

```bash
# Nur Domain angeben - Sitemap wird automatisch gesucht
console-error-scanner https://www.example.com

# Oder direkte Sitemap-URL
console-error-scanner https://www.example.com/sitemap.xml

# Mit mehr parallelen Tabs (Standard: 8)
console-error-scanner https://www.example.com --concurrency 12

# Englische Oberflaeche
console-error-scanner https://www.example.com --lang en

# Nur bestimmte URLs scannen
console-error-scanner https://www.example.com --filter /produkte

# Nur console.error erfassen (ohne Warnings)
console-error-scanner https://www.example.com --console-level error

# Authentifizierung per Cookie (z.B. fuer Testumgebungen)
console-error-scanner https://test.example.com --cookie auth=token123

# Mehrere Cookies setzen
console-error-scanner https://test.example.com --cookie auth=token123 --cookie session=abc

# Bekannte Fehler per Whitelist ignorieren
console-error-scanner https://www.example.com --whitelist whitelist.json

# Cookie-Consent NICHT akzeptieren (Banner wird nur per CSS versteckt)
console-error-scanner https://www.example.com --no-consent

# Lazy-Loading-Scroll deaktivieren (Seite wird nicht durchgescrollt)
console-error-scanner https://www.example.com --no-scroll

# Reports automatisch speichern
console-error-scanner https://www.example.com --output-json report.json --output-html report.html

# Browser sichtbar starten (Debugging)
console-error-scanner https://www.example.com --no-headless
```

## CLI-Parameter

| Parameter | Kurz | Default | Beschreibung |
|-----------|------|---------|-------------|
| `URL` | | (pflicht) | URL der Website oder Sitemap (XML). Bei Domain-URLs wird die Sitemap automatisch gesucht |
| `--concurrency` | `-c` | 8 | Max parallele Browser-Tabs |
| `--timeout` | `-t` | 60 | Timeout pro Seite in Sekunden |
| `--output-json` | | | JSON-Report automatisch speichern |
| `--output-html` | | | HTML-Report automatisch speichern |
| `--lang` | | de | Sprache der Oberfläche (de, en) |
| `--no-headless` | | false | Browser sichtbar starten |
| `--filter` | `-f` | | Nur URLs scannen die TEXT enthalten |
| `--console-level` | | warn | error, warn, all |
| `--user-agent` | | Chrome 131 | Custom User-Agent String |
| `--cookie` | | | Cookie setzen (NAME=VALUE), mehrfach verwendbar |
| `--whitelist` | `-w` | | Pfad zur Whitelist-JSON (bekannte Fehler ignorieren) |
| `--no-consent` | | false | Cookie-Consent NICHT akzeptieren (Banner wird nur versteckt) |
| `--no-scroll` | | false | Seite nicht scrollen (kein Lazy-Loading Trigger) |

### Console-Level

- **error** - Nur `console.error()` erfassen
- **warn** - `console.error()` + `console.warn()` (Standard)
- **all** - Alle Console-Ausgaben (`error`, `warn`, `info`, `log`, `debug`)

## Features

- **Sitemap Auto-Discovery**: Bei Domain-URLs wird die Sitemap automatisch über robots.txt und typische Pfade (/sitemap.xml, /sitemap/sitemap.xml, ...) gefunden. Falls keine Sitemap vorhanden ist, kann mit dem [Sitemap Generator](https://michaelblaess.github.io/sitemap-generator) eine erstellt und als URL übergeben werden
- **Lazy-Loading Trigger**: Scrollt Seiten automatisch durch, um per IntersectionObserver nachgeladene Bilder zu triggern. Erkennt fehlende Bilder (404) unterhalb des Viewports. Per `g`-Taste oder `--no-scroll` umschaltbar
- **Consent-Banner Behandlung**: 3-Phasen-Consent (JavaScript-API, Button-Klick Fallback, CSS-Hide) für Usercentrics, OneTrust, CookieBot und generische Banner. Per `n`-Taste oder `--no-consent` umschaltbar zwischen Akzeptieren und nur Verstecken
- **CSP-Violation Erkennung**: Erkennt Content Security Policy Verstöße via `pageerror` Events
- **Fehlgeschlagene Requests**: Erkennt abgebrochene/fehlgeschlagene Netzwerk-Requests
- **Cookie-Authentifizierung**: Zugriff auf geschützte Testumgebungen per `--cookie` Parameter
- **Whitelist**: Bekannte Fehler per Wildcard-Pattern ignorieren (z.B. attachShadow, AppInsights)
- **Live-Updates**: Ergebnisse erscheinen sofort während des Scans in der Tabelle
- **Auto-Scroll**: Tabelle scrollt automatisch zur aktuell gescannten URL mit
- **Mehrsprachig**: Deutsch und Englisch (`--lang en`), alle UI-Texte über JSON-Sprachdateien
- **Settings-Persistenz**: Theme, Consent-Modus, Scroll-Modus und Sprache werden gespeichert
- **Scan-History**: Vorherige Scans können per `h`-Taste wiederhergestellt werden

## Tastenkürzel in der TUI

| Taste | Aktion |
|-------|--------|
| `s` | Scan starten |
| `r` | HTML + JSON Reports speichern |
| `t` | Top 10 Fehler anzeigen |
| `h` | Scan-History anzeigen |
| `n` | Consent-Toggle (AN = akzeptieren, AUS = nur Banner verstecken) |
| `g` | Scroll-Toggle (AN = Lazy-Loading triggern, AUS = nicht scrollen) |
| `l` | Log-Bereich ein/ausblenden |
| `e` | Nur fehlerhafte URLs anzeigen |
| `c` | Log in Zwischenablage kopieren |
| `/` | Filter-Eingabe fokussieren |
| `ESC` | Filter leeren |
| `+` / `-` | Log-Bereich vergrößern/verkleinern |
| `i` | Info-Dialog |
| `q` | Beenden |

## Whitelist

Mit einer Whitelist-Datei können bekannte, irrelevante Fehler ignoriert werden. Die Datei ist im JSON-Format:

```json
{
  "description": "Known Bugs - diese Fehler werden ignoriert",
  "patterns": [
    "*Failed to execute 'attachShadow' on 'Element'*",
    "*AppInsights nicht gefunden*",
    "*carouselWrapper is not initialized yet*",
    "HTTP 404:*tracking.js*",
    "*https://googleads.g.doubleclick.net*"
  ]
}
```

**Pattern-Syntax** (fnmatch):
- `*` = beliebig viele Zeichen
- `?` = genau ein Zeichen
- Matching ist **case-insensitive**
- Wird gegen die Fehlermeldung (`PageError.message`) gematcht
- Betrifft **alle Fehlertypen**: Console Errors, Warnings, CSP Violations, HTTP-Fehler

**Status-Anzeige**:
- **OK** - Keine Fehler
- **WARN** - Nur Warnings (keine echten Fehler)
- **ERR** - Echte (nicht-whitelisted) Fehler vorhanden
- **IGN** - Seite hat nur whitelisted Fehler (gelb)
- Whitelisted Fehler erscheinen in einer eigenen "Ignored"-Spalte und als gedimmte Sektion in der Detail-Ansicht

Eine Beispiel-Whitelist liegt im Repository unter `whitelist.json`.

## Browser-Strategie

Der Scanner versucht beim Start den **System-Chrome** zu nutzen (`channel="chrome"`).
Falls Chrome nicht installiert ist, wird das **gebundelte Chromium** als Fallback verwendet.

| Variante | Größe | Voraussetzung |
|----------|---------|---------------|
| System-Chrome (bevorzugt) | 0 MB extra | Chrome installiert |
| Gebundeltes Chromium (Fallback) | +150 MB | Keine |

## Robustheit

- Retry-Logik: 3 Versuche pro Seite mit exponential Backoff (5s, 10s, 20s)
- Browser-Recovery: Automatischer Neustart bei Crash
- Netzwerk-Check: HEAD-Request vor jedem Retry
- Graceful Degradation: Fehlgeschlagene URLs werden markiert, Scan läuft weiter
- Fehler-Deduplizierung: Doppelte Fehlermeldungen werden automatisch zusammengeführt

---

## Entwickler

### Setup

```bash
# Windows
setup-dev-environment.bat
run.bat https://www.example.com

# Linux/macOS
./setup-dev-environment.sh
./run.sh https://www.example.com
```

Das Setup erstellt eine virtuelle Umgebung (`.venv`), installiert alle Abhängigkeiten und lädt den Chromium-Browser herunter.

Voraussetzungen: Python 3.10+

#### Manuelle Installation

```bash
# 1. Virtuelle Umgebung erstellen
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/macOS

# 2. Paket installieren
pip install -e .

# 3. Playwright Chromium-Browser installieren
playwright install chromium
```

Bei SSL-Problemen im Firmennetz:
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -e .
```

### Lokaler Build (Standalone-EXE)

```bash
# Windows
build-dist.bat

# Linux/macOS
./build-dist.sh
```

Erstellt `dist/console-error-scanner/` - den Ordner zippen und weitergeben. Kein Python nötig auf dem Zielrechner.

### Release erstellen

1. Version-Tag setzen und pushen:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions baut automatisch für alle Plattformen:
   - `console-error-scanner-win-x64.zip`
   - `console-error-scanner-linux-x64.tar.gz`
   - `console-error-scanner-macos-arm64.tar.gz`

3. Release wird automatisch auf GitHub erstellt mit den Build-Artefakten.

### Architektur

```
src/console_error_scanner/
  __main__.py           CLI Entry Point (argparse)
  app.py                Textual App (Hauptklasse)
  app.tcss              Textual CSS (Layout)
  models/
    scan_result.py      ScanResult, PageError, Enums
    sitemap.py          Sitemap-Parser + Auto-Discovery
    history.py          Scan-History Persistenz
    settings.py         Settings Persistenz (Theme, Consent, Scroll)
    whitelist.py        Whitelist (Wildcard-Pattern Matching)
  i18n.py               Internationalisierung (t()-Funktion)
  locale/
    de.json             Deutsche Sprachdatei
    en.json             Englische Sprachdatei
  widgets/
    results_table.py    DataTable mit Filter + Auto-Scroll
    error_detail_view.py  Detail-Ansicht rechts
    summary_panel.py    Zusammenfassung oben
  screens/
    error_detail.py     Modal: Fehlerdetails
    top_errors.py       Modal: Top 10 Fehler Chart
    history.py          Modal: Scan-History
    about.py            Modal: About-Dialog
  services/
    scanner.py          Playwright Scanner (Retry, Recovery)
    reporter.py         HTML + JSON Report-Generator
```
