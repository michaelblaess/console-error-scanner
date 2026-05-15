# Console Error Scanner

<p align="center">
  <img src="docs/flags/gb.svg" height="13" alt=""> <b>English</b> ·
  <img src="docs/flags/de.svg" height="13" alt=""> <a href="README.de.md">Deutsch</a>
</p>

---

[![Stars](https://img.shields.io/github/stars/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=fbbf24)](https://github.com/michaelblaess/console-error-scanner/stargazers)
[![Forks](https://img.shields.io/github/forks/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=34d399)](https://github.com/michaelblaess/console-error-scanner/network/members)
[![Issues](https://img.shields.io/github/issues/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=f87171)](https://github.com/michaelblaess/console-error-scanner/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/michaelblaess/console-error-scanner?logo=github&logoColor=white&color=a78bfa)](https://github.com/michaelblaess/console-error-scanner/pulls)

[![Last Commit](https://img.shields.io/github/last-commit/michaelblaess/console-error-scanner?logo=git&logoColor=white&color=3b82f6)](https://github.com/michaelblaess/console-error-scanner/commits/main)
[![License](https://img.shields.io/badge/license-Apache_2.0-3b82f6)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3b82f6?logo=python&logoColor=white)](https://www.python.org/)

TUI tool for automatically scanning websites for JavaScript console errors and HTTP errors (404, 5xx).
The input is a website URL or sitemap URL (XML). For domain URLs, the sitemap is found automatically via robots.txt and typical paths. Results are displayed live in a terminal UI and can be exported as HTML and JSON reports.

## Screenshots

### Main view
![Main view](docs/screenshots/01-main.png)

### Top 10 errors
![Top 10 errors](docs/screenshots/02-top-10-errors.png)

### Scan history
![Scan history](docs/screenshots/03-history.png)

## Installation

No dependencies needed - no Python, no Git, no Chrome.

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/michaelblaess/console-error-scanner/main/install.ps1 | iex
```

Then open a new terminal and get started:

```bash
console-error-scanner https://www.example.com
```

### Updating

Simply run the installer again - it detects an existing installation and overwrites it.

### Uninstalling

```bash
# Linux/macOS
rm -rf ~/.console-error-scanner ~/.local/bin/console-error-scanner

# Windows PowerShell
Remove-Item -Recurse "$env:LOCALAPPDATA\console-error-scanner"
```

### Installation paths

| OS | Program | Wrapper / PATH |
|----|----------|----------------|
| Linux | `~/.console-error-scanner/` | `~/.local/bin/console-error-scanner` |
| macOS | `~/.console-error-scanner/` | `~/.local/bin/console-error-scanner` |
| Windows | `%LOCALAPPDATA%\console-error-scanner\` | `...\bin\console-error-scanner.cmd` (automatically in PATH) |

## Usage

```bash
# Just provide the domain - sitemap is found automatically
console-error-scanner https://www.example.com

# Or a direct sitemap URL
console-error-scanner https://www.example.com/sitemap.xml

# With more parallel tabs (default: 8)
console-error-scanner https://www.example.com --concurrency 12

# English interface
console-error-scanner https://www.example.com --lang en

# Scan only specific URLs
console-error-scanner https://www.example.com --filter /produkte

# Capture only console.error (without warnings)
console-error-scanner https://www.example.com --console-level error

# Authentication via cookie (e.g. for test environments)
console-error-scanner https://test.example.com --cookie auth=token123

# Set multiple cookies
console-error-scanner https://test.example.com --cookie auth=token123 --cookie session=abc

# Ignore known errors via whitelist
console-error-scanner https://www.example.com --whitelist whitelist.json

# Do NOT accept cookie consent (banner is only hidden via CSS)
console-error-scanner https://www.example.com --no-consent

# Disable lazy-loading scroll (the page is not scrolled through)
console-error-scanner https://www.example.com --no-scroll

# Save reports automatically
console-error-scanner https://www.example.com --output-json report.json --output-html report.html

# Start browser visibly (debugging)
console-error-scanner https://www.example.com --no-headless
```

## CLI parameters

| Parameter | Short | Default | Description |
|-----------|------|---------|-------------|
| `URL` | | (required) | URL of the website or sitemap (XML). For domain URLs the sitemap is found automatically |
| `--concurrency` | `-c` | 8 | Max parallel browser tabs |
| `--timeout` | `-t` | 60 | Timeout per page in seconds |
| `--output-json` | | | Save JSON report automatically |
| `--output-html` | | | Save HTML report automatically |
| `--lang` | | de | Interface language (de, en) |
| `--no-headless` | | false | Start browser visibly |
| `--filter` | `-f` | | Scan only URLs containing TEXT |
| `--console-level` | | warn | error, warn, all |
| `--user-agent` | | Chrome 131 | Custom user-agent string |
| `--cookie` | | | Set cookie (NAME=VALUE), can be used multiple times |
| `--whitelist` | `-w` | | Path to the whitelist JSON (ignore known errors) |
| `--no-consent` | | false | Do NOT accept cookie consent (banner is only hidden) |
| `--no-scroll` | | false | Do not scroll the page (no lazy-loading trigger) |

### Console level

- **error** - Capture only `console.error()`
- **warn** - `console.error()` + `console.warn()` (default)
- **all** - All console output (`error`, `warn`, `info`, `log`, `debug`)

## Features

- **Sitemap auto-discovery**: For domain URLs the sitemap is found automatically via robots.txt and typical paths (/sitemap.xml, /sitemap/sitemap.xml, ...). If no sitemap exists, one can be created with the [Sitemap Generator](https://michaelblaess.github.io/sitemap-generator) and passed as a URL
- **Lazy-loading trigger**: Automatically scrolls through pages to trigger images loaded via IntersectionObserver. Detects missing images (404) below the viewport. Toggleable via the `g` key or `--no-scroll`
- **Consent banner handling**: 3-phase consent (JavaScript API, button-click fallback, CSS hide) for Usercentrics, OneTrust, CookieBot and generic banners. Toggleable via the `n` key or `--no-consent` between accepting and only hiding
- **CSP violation detection**: Detects Content Security Policy violations via `pageerror` events
- **Failed requests**: Detects aborted/failed network requests
- **Cookie authentication**: Access to protected test environments via the `--cookie` parameter
- **Whitelist**: Ignore known errors via wildcard patterns (e.g. attachShadow, AppInsights)
- **Live updates**: Results appear immediately in the table during the scan
- **Auto-scroll**: The table scrolls along automatically to the currently scanned URL
- **Multilingual**: German and English (`--lang en`), all UI texts via JSON language files
- **Settings persistence**: Theme, consent mode, scroll mode and language are saved
- **Scan history**: Previous scans can be restored via the `h` key

## Keyboard shortcuts in the TUI

| Key | Action |
|-------|--------|
| `s` | Start scan |
| `r` | Save HTML + JSON reports |
| `t` | Show top 10 errors |
| `h` | Show scan history |
| `n` | Consent toggle (ON = accept, OFF = only hide banner) |
| `g` | Scroll toggle (ON = trigger lazy-loading, OFF = do not scroll) |
| `l` | Show/hide log area |
| `e` | Show only failed URLs |
| `c` | Copy log to clipboard |
| `/` | Focus the filter input |
| `ESC` | Clear filter |
| `+` / `-` | Enlarge/shrink the log area |
| `i` | Info dialog |
| `q` | Quit |

## Whitelist

A whitelist file can be used to ignore known, irrelevant errors. The file is in JSON format:

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

**Pattern syntax** (fnmatch):
- `*` = any number of characters
- `?` = exactly one character
- Matching is **case-insensitive**
- Matched against the error message (`PageError.message`)
- Affects **all error types**: console errors, warnings, CSP violations, HTTP errors

**Status display**:
- **OK** - No errors
- **WARN** - Only warnings (no real errors)
- **ERR** - Real (non-whitelisted) errors present
- **IGN** - Page has only whitelisted errors (yellow)
- Whitelisted errors appear in their own "Ignored" column and as a dimmed section in the detail view

An example whitelist is included in the repository under `whitelist.json`.

## Browser strategy

On startup the scanner tries to use the **system Chrome** (`channel="chrome"`).
If Chrome is not installed, the **bundled Chromium** is used as a fallback.

| Variant | Size | Requirement |
|----------|---------|---------------|
| System Chrome (preferred) | 0 MB extra | Chrome installed |
| Bundled Chromium (fallback) | +150 MB | None |

## Robustness

- Retry logic: 3 attempts per page with exponential backoff (5s, 10s, 20s)
- Browser recovery: automatic restart on crash
- Network check: HEAD request before each retry
- Graceful degradation: failed URLs are flagged, the scan continues
- Error deduplication: duplicate error messages are merged automatically

---

## Developers

### Setup

```bash
# Windows
setup-dev-environment.bat
run.bat https://www.example.com

# Linux/macOS
./setup-dev-environment.sh
./run.sh https://www.example.com
```

The setup creates a virtual environment (`.venv`), installs all dependencies and downloads the Chromium browser.

Requirements: Python 3.10+

#### Manual installation

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate  # Linux/macOS

# 2. Install the package
pip install -e .

# 3. Install the Playwright Chromium browser
playwright install chromium
```

For SSL problems on a corporate network:
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -e .
```

### Local build (standalone EXE)

```bash
# Windows
build-dist.bat

# Linux/macOS
./build-dist.sh
```

Creates `dist/console-error-scanner/` - zip the folder and distribute it. No Python needed on the target machine.

### Creating a release

1. Set and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions builds automatically for all platforms:
   - `console-error-scanner-win-x64.zip`
   - `console-error-scanner-linux-x64.tar.gz`
   - `console-error-scanner-macos-arm64.tar.gz`

3. The release is created automatically on GitHub with the build artifacts.

### Architecture

```
src/console_error_scanner/
  __main__.py           CLI entry point (argparse)
  app.py                Textual app (main class)
  app.tcss              Textual CSS (layout)
  models/
    scan_result.py      ScanResult, PageError, enums
    sitemap.py          Sitemap parser + auto-discovery
    history.py          Scan history persistence
    settings.py         Settings persistence (theme, consent, scroll)
    whitelist.py        Whitelist (wildcard pattern matching)
  i18n.py               Internationalization (t() function)
  locale/
    de.json             German language file
    en.json             English language file
  widgets/
    results_table.py    DataTable with filter + auto-scroll
    error_detail_view.py  Detail view on the right
    summary_panel.py    Summary at the top
  screens/
    error_detail.py     Modal: error details
    top_errors.py       Modal: top 10 errors chart
    history.py          Modal: scan history
    about.py            Modal: about dialog
  services/
    scanner.py          Playwright scanner (retry, recovery)
    reporter.py         HTML + JSON report generator
```
