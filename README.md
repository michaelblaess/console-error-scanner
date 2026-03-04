# Console Error Scanner

TUI-Tool zum automatischen Scannen von Websites auf JavaScript Console-Errors und HTTP-Fehler (404, 5xx).
Eingabe ist eine Website-URL oder Sitemap-URL (XML). Bei Domain-URLs wird die Sitemap automatisch ueber robots.txt und typische Pfade gefunden. Ergebnisse werden live in einer Terminal-UI angezeigt und koennen als HTML- und JSON-Reports exportiert werden.

## Installation

Keine Abhaengigkeiten noetig - kein Python, kein Git, kein Chrome.

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.ps1 | iex
```

Danach ein neues Terminal oeffnen und loslegen:

```bash
console-error-scanner https://www.example.com
```

### Aktualisieren

Einfach den Installer erneut ausfuehren - erkennt vorhandene Installation und ueberschreibt.

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
| `--timeout` | `-t` | 30 | Timeout pro Seite in Sekunden |
| `--output-json` | | | JSON-Report automatisch speichern |
| `--output-html` | | | HTML-Report automatisch speichern |
| `--no-headless` | | false | Browser sichtbar starten |
| `--filter` | `-f` | | Nur URLs scannen die TEXT enthalten |
| `--console-level` | | warn | error, warn, all |
| `--user-agent` | | Chrome 131 | Custom User-Agent String |
| `--cookie` | | | Cookie setzen (NAME=VALUE), mehrfach verwendbar |
| `--whitelist` | `-w` | | Pfad zur Whitelist-JSON (bekannte Fehler ignorieren) |
| `--no-consent` | | false | Cookie-Consent NICHT akzeptieren (Banner wird nur versteckt) |

### Console-Level

- **error** - Nur `console.error()` erfassen
- **warn** - `console.error()` + `console.warn()` (Standard)
- **all** - Alle Console-Ausgaben (`error`, `warn`, `info`, `log`, `debug`)

## Features

- **Sitemap Auto-Discovery**: Bei Domain-URLs wird die Sitemap automatisch ueber robots.txt und typische Pfade (/sitemap.xml, /sitemap/sitemap.xml, ...) gefunden
- **Consent-Banner Behandlung**: 3-Phasen-Consent (JavaScript-API, Button-Klick Fallback, CSS-Hide) fuer Usercentrics, OneTrust, CookieBot und generische Banner. Per `n`-Taste oder `--no-consent` umschaltbar zwischen Akzeptieren und nur Verstecken
- **CSP-Violation Erkennung**: Erkennt Content Security Policy Verstoesze via `pageerror` Events
- **Fehlgeschlagene Requests**: Erkennt abgebrochene/fehlgeschlagene Netzwerk-Requests
- **Cookie-Authentifizierung**: Zugriff auf geschuetzte Testumgebungen per `--cookie` Parameter
- **Whitelist**: Bekannte Fehler per Wildcard-Pattern ignorieren (z.B. attachShadow, AppInsights)
- **Live-Updates**: Ergebnisse erscheinen sofort waehrend des Scans in der Tabelle
- **Auto-Scroll**: Tabelle scrollt automatisch zur aktuell gescannten URL mit
- **Settings-Persistenz**: Theme und Consent-Modus werden gespeichert
- **Scan-History**: Vorherige Scans koennen per `h`-Taste wiederhergestellt werden

## Tastenkuerzel in der TUI

| Taste | Aktion |
|-------|--------|
| `s` | Scan starten |
| `r` | HTML + JSON Reports speichern |
| `t` | Top 10 Fehler anzeigen |
| `h` | Scan-History anzeigen |
| `n` | Consent-Toggle (AN = akzeptieren, AUS = nur Banner verstecken) |
| `l` | Log-Bereich ein/ausblenden |
| `e` | Nur fehlerhafte URLs anzeigen |
| `c` | Log in Zwischenablage kopieren |
| `/` | Filter-Eingabe fokussieren |
| `ESC` | Filter leeren |
| `+` / `-` | Log-Bereich vergroessern/verkleinern |
| `i` | Info-Dialog |
| `q` | Beenden |

## Whitelist

Mit einer Whitelist-Datei koennen bekannte, irrelevante Fehler ignoriert werden. Die Datei ist im JSON-Format:

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

| Variante | Groesse | Voraussetzung |
|----------|---------|---------------|
| System-Chrome (bevorzugt) | 0 MB extra | Chrome installiert |
| Gebundeltes Chromium (Fallback) | +150 MB | Keine |

## Robustheit

- Retry-Logik: 3 Versuche pro Seite mit exponential Backoff (5s, 10s, 20s)
- Browser-Recovery: Automatischer Neustart bei Crash
- Netzwerk-Check: HEAD-Request vor jedem Retry
- Graceful Degradation: Fehlgeschlagene URLs werden markiert, Scan laeuft weiter
- Fehler-Deduplizierung: Doppelte Fehlermeldungen werden automatisch zusammengefuehrt

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

Das Setup erstellt eine virtuelle Umgebung (`.venv`), installiert alle Abhaengigkeiten und laedt den Chromium-Browser herunter.

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

Erstellt `dist/console-error-scanner/` - den Ordner zippen und weitergeben. Kein Python noetig auf dem Zielrechner.

### Release erstellen

1. Version-Tag setzen und pushen:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions baut automatisch fuer alle Plattformen:
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
    settings.py         Settings Persistenz (Theme, Consent)
    whitelist.py        Whitelist (Wildcard-Pattern Matching)
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
