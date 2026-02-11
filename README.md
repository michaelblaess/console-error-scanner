# Console Error Scanner

TUI-Tool zum automatischen Scannen von Websites auf JavaScript Console-Errors und HTTP-Fehler (404, 5xx).
Eingabe ist eine Sitemap-URL (XML). Ergebnisse werden live in einer Terminal-UI angezeigt und koennen als HTML- und JSON-Reports exportiert werden.

## Voraussetzungen

- Python 3.10+
- Windows (getestet), Linux und macOS sollten funktionieren

## Schnell-Setup (empfohlen)

```bash
# 1. setup.bat doppelklicken oder ausfuehren:
setup.bat

# 2. Starten:
run.bat https://www.example.com/sitemap.xml
```

Das Setup erstellt eine virtuelle Umgebung (`.venv`), installiert alle Abhaengigkeiten und laedt den Chromium-Browser herunter.

## Manuelle Installation

```bash
# 1. Virtuelle Umgebung erstellen
python -m venv .venv
.venv\Scripts\activate

# 2. Paket installieren
pip install -e .

# 3. Playwright Chromium-Browser installieren
playwright install chromium
```

Bei SSL-Problemen im Firmennetz:
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -e .
```

## Verwendung

```bash
# Einfacher Start - TUI mit Sitemap
run.bat https://www.example.com/sitemap.xml

# Mit mehr parallelen Tabs (Standard: 8)
run.bat https://www.example.com/sitemap.xml --concurrency 12

# Nur bestimmte URLs scannen
run.bat https://www.example.com/sitemap.xml --filter /produkte

# Nur console.error erfassen (ohne Warnings)
run.bat https://www.example.com/sitemap.xml --console-level error

# Authentifizierung per Cookie (z.B. fuer Testumgebungen)
run.bat https://test.example.com/sitemap.xml --cookie auth=token123

# Mehrere Cookies setzen
run.bat https://test.example.com/sitemap.xml --cookie auth=token123 --cookie session=abc

# Reports automatisch speichern (fuer Azure Pipeline)
run.bat https://www.example.com/sitemap.xml --output-json report.json --output-html report.html

# Browser sichtbar starten (Debugging)
run.bat https://www.example.com/sitemap.xml --no-headless
```

## CLI-Parameter

| Parameter | Kurz | Default | Beschreibung |
|-----------|------|---------|-------------|
| `SITEMAP_URL` | | (pflicht) | URL der Sitemap (XML) |
| `--concurrency` | `-c` | 8 | Max parallele Browser-Tabs |
| `--timeout` | `-t` | 30 | Timeout pro Seite in Sekunden |
| `--output-json` | | | JSON-Report automatisch speichern |
| `--output-html` | | | HTML-Report automatisch speichern |
| `--no-headless` | | false | Browser sichtbar starten |
| `--filter` | `-f` | | Nur URLs scannen die TEXT enthalten |
| `--console-level` | | warn | error, warn, all |
| `--user-agent` | | Chrome 131 | Custom User-Agent String |
| `--cookie` | | | Cookie setzen (NAME=VALUE), mehrfach verwendbar |

### Console-Level

- **error** - Nur `console.error()` erfassen
- **warn** - `console.error()` + `console.warn()` (Standard)
- **all** - Alle Console-Ausgaben (`error`, `warn`, `info`, `log`, `debug`)

## Features

- **Consent-Banner Auto-Accept**: Erkennt und akzeptiert automatisch Usercentrics, OneTrust und CookieBot, damit auch Tracking-Scripts geladen und geprueft werden
- **CSP-Violation Erkennung**: Erkennt Content Security Policy Verstoesze via `pageerror` Events
- **Fehlgeschlagene Requests**: Erkennt abgebrochene/fehlgeschlagene Netzwerk-Requests
- **Cookie-Authentifizierung**: Zugriff auf geschuetzte Testumgebungen per `--cookie` Parameter
- **Live-Updates**: Ergebnisse erscheinen sofort waehrend des Scans in der Tabelle

## Tastenkuerzel in der TUI

| Taste | Aktion |
|-------|--------|
| `s` | Scan starten |
| `r` | HTML + JSON Reports speichern |
| `t` | Top 10 Fehler anzeigen |
| `l` | Log-Bereich ein/ausblenden |
| `e` | Nur fehlerhafte URLs anzeigen |
| `c` | Log in Zwischenablage kopieren |
| `/` | Filter-Eingabe fokussieren |
| `ESC` | Filter leeren |
| `+` / `-` | Log-Bereich vergroessern/verkleinern |
| `i` | Info-Dialog |
| `q` | Beenden |

## Architektur

```
src/console_error_scanner/
  __main__.py           CLI Entry Point (argparse)
  app.py                Textual App (Hauptklasse)
  app.tcss              Textual CSS (Layout)
  models/
    scan_result.py      ScanResult, PageError, Enums
    sitemap.py          Sitemap-Parser (XML -> URLs)
  widgets/
    results_table.py    DataTable mit Filter
    error_detail_view.py  Detail-Ansicht rechts
    summary_panel.py    Zusammenfassung oben
  screens/
    error_detail.py     Modal: Fehlerdetails
    top_errors.py       Modal: Top 10 Fehler Chart
    about.py            Modal: About-Dialog
  services/
    scanner.py          Playwright Scanner (Retry, Recovery)
    reporter.py         HTML + JSON Report-Generator
```

## Robustheit

- Retry-Logik: 3 Versuche pro Seite mit exponential Backoff (5s, 10s, 20s)
- Browser-Recovery: Automatischer Neustart bei Crash
- Netzwerk-Check: HEAD-Request vor jedem Retry
- Graceful Degradation: Fehlgeschlagene URLs werden markiert, Scan laeuft weiter
