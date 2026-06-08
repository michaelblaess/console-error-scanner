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

CLI flags override the persisted settings for the current run. Everything except the URL itself has a sensible default in `~/.console-error-scanner/settings.json` and can also be changed at runtime via the settings dialog (`s`).

| Parameter | Short | Default | Description |
|-----------|------|---------|-------------|
| `URL_OR_FILE` | | (optional) | Website URL, sitemap URL or local sitemap.xml. For domain URLs the sitemap is found automatically. If omitted, the TUI asks for the URL on `c` |
| `--concurrency` | `-c` | settings (8) | Max parallel browser tabs |
| `--timeout` | `-t` | settings (60) | Timeout per page in seconds |
| `--output-json` | | | Save JSON report automatically and exit |
| `--output-html` | | | Save HTML report automatically and exit |
| `--lang` | | settings (de) | Interface language (de, en) |
| `--no-headless` | | false | Start browser visibly (debugging) |
| `--filter` | `-f` | | Scan only URLs containing TEXT |
| `--console-level` | | settings (warn) | error, warn, all |
| `--user-agent` | | Chrome 131 | Custom user-agent string |
| `--cookie` | | | Set cookie (NAME=VALUE), can be used multiple times |
| `--whitelist` | `-w` | settings | Path to the whitelist JSON (ignore known errors) |
| `--no-consent` | | false | Do NOT accept cookie consent (banner is only hidden) |
| `--no-scroll` | | false | Do not scroll the page (no lazy-loading trigger) |

### Console level

- **error** - Capture only `console.error()`
- **warn** - `console.error()` + `console.warn()` (default)
- **all** - All console output (`error`, `warn`, `info`, `log`, `debug`)

> Info/Log/Debug are **not** captured as long as the level is `warn`.

## Features

- **Sitemap auto-discovery**: For domain URLs the sitemap is found automatically via robots.txt and typical paths (/sitemap.xml, /sitemap/sitemap.xml, ...). If no sitemap exists, one can be created with the [Sitemap Generator](https://michaelblaess.github.io/sitemap-generator) and passed as a URL
- **Sitemap file picker**: `m` opens a file-open dialog ([textual-fspicker](https://github.com/davep/textual-fspicker)) for local sitemap.xml files - alternative to typing the URL
- **Page preview**: Optional Playwright sidecar renders a screenshot of the selected URL in the detail pane (TGP/Sixel terminals) with persistent disk cache (HTTP validator + TTL). Right-click on the preview copies the image to the clipboard (drag-and-drop into JIRA / Slack)
- **Site score**: After each scan a 0-100 score (grade A-F) is computed from the share of error-free pages and the average page weight - the weighting is configurable. It is shown color-coded in the header title and in an auto-opening summary modal with the findings and the biggest pages/resources ("big fish") as bar charts
- **Diet advisor**: Right-click a row -> "Diet advisor" opens a per-page bar chart of the largest resources (the "fat chunks") so you immediately see what bloats a page
- **Right-click context menu** on result rows: open URL in browser, copy URL, show details, diet advisor, copy details, rescan a single URL, toggle errors-only filter
- **Page-weight column**: The "Size" column shows the real transfer weight (sum of same-host resources via the actual response body size, streamed video/audio excluded, each resource counted once). A configurable threshold highlights oversized pages red with a warning marker; hover the column header for the exact definition
- **Load time & requests**: The "Time" column shows the browser load time up to the Load event (Navigation Timing API, same semantics as DevTools "Load"), the "Req" column the total number of requests of the page (like the Edge network monitor). Both are sortable; the detail pane additionally shows DOMContentLoaded. Note: during a parallel scan the absolute load times are subject to contention and only comparable relatively within a scan (see column header tooltip)
- **Sortable columns**: Click any column header to sort ascending/descending with ▲/▼ indicator
- **Lazy-loading trigger**: Automatically scrolls through pages to trigger images loaded via IntersectionObserver. Detects missing images (404) below the viewport
- **Consent banner handling**: 3-phase consent (JavaScript API, button-click fallback, CSS hide) for Usercentrics, OneTrust, CookieBot and generic banners. Settings toggle between accepting and only hiding
- **CSP violation detection**: Detects Content Security Policy violations via `pageerror` events
- **Failed requests**: Detects aborted/failed network requests
- **Cookie authentication**: Access to protected test environments
- **Whitelist**: Ignore known errors via wildcard patterns (e.g. attachShadow, AppInsights). Press `w` to inspect the loaded patterns and their hit counts
- **Hover-clickable links** throughout: every URL and file path in logs, detail pane, dialogs and notifications opens in the OS default browser/file manager - no CTRL needed
- **Settings dialog** (`s`): centralized config for concurrency, timeout, console-level, headless, consent, lazy-loading, whitelist path, user-agent, cookies, page preview, the size-warning threshold (MB) and the site-score weighting - with info-icon tooltips and a storage-paths tab
- **Live updates**: Results appear immediately in the table during the scan
- **Auto-scroll**: The table scrolls along automatically to the currently scanned URL
- **36 retro themes**: Pick via Ctrl+P or cycle with `t` (persistent)
- **Multilingual**: German and English (`--lang en`), all UI texts via JSON language files
- **Crash guard**: Unhandled exceptions show a copyable error screen instead of killing the app
- **Scan history**: Previous scan URLs can be restored via `h`

## Keyboard shortcuts in the TUI

The bindings are unified across all of Michael's TUIs (`c` = crawl, `s` = settings, `t` = theme, ...).

| Key | Action |
|-------|--------|
| `c` | Start scan (asks for URL if none is loaded) |
| `m` | Load a local sitemap file via file picker |
| `s` | Settings dialog |
| `h` | Scan history |
| `r` | Save HTML + JSON reports |
| `w` | Show the loaded whitelist patterns + hit counts |
| `e` | Show only pages with errors (toggle) |
| `t` | Cycle to the next retro theme (Ctrl+P for full picker) |
| `l` | Show/hide log panel (drag the splitter to resize) |
| `d` | Copy the detail pane to the clipboard |
| `F10` | Top 10 errors chart |
| `/` | Focus the filter input |
| `ESC` | Clear filter / close dialog |
| `i` | About dialog |
| `q` | Quit |

**On the preview image** (when page preview is enabled in settings):
- Right-click = copy screenshot to clipboard
- Shift + right-click = save screenshot as PNG file

**On a result row**:
- Single left-click selects the row; **double-click (or Enter) opens the detail window**
- Right-click = context menu with `Open URL in browser`, `Copy URL`, `Show details`, `Diet advisor`, `Copy details`, `Rescan this URL`, `Show errors only / Show all`

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

The whitelist path is configured in the settings dialog (`s` → Whitelist path) and persisted; alternatively pass `--whitelist <path>` on the CLI. Press `w` in the TUI to open the **whitelist viewer** - a modal that lists every loaded pattern with its hit count against the current scan.

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
./bootstrap.ps1
./run.ps1 https://www.example.com

# Linux/macOS
./bootstrap.sh
./run.sh https://www.example.com
```

The bootstrap script uses `uv` to create a virtual environment (`.venv`), syncs the runtime + dev dependencies from `uv.lock`, installs Nuitka for builds and downloads the Chromium browser. Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

#### Manual installation

```bash
# 1. Create virtual environment
uv sync --extra dev

# 2. Install the Playwright Chromium browser
uv run playwright install chromium
```

For SSL problems on a corporate network (Zscaler etc.), see the `bootstrap.ps1` script: set `UV_NATIVE_TLS=1`, clear `SSL_CERT_FILE`, and uv falls back to the Windows certificate store.

### Local build (standalone binary)

The build is based on **Nuitka** (compiles Python to a native binary, no interpreter on the target machine):

```bash
# Windows
./compile-win64.ps1

# Linux  (needs gcc + patchelf + python3-dev)
./compile-linux.sh

# macOS  (needs Xcode Command Line Tools)
./compile-macos.sh
```

Creates `dist/console-error-scanner/` (~180 MB with Chromium headless shell) and a versioned `.zip` / `.tar.gz` next to it.

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
  __main__.py           CLI entry point (argparse, pre-init textual-image)
  app.py                Textual app (CrashGuard, LogRouter, ClickableLinks)
  app.tcss              Textual CSS (layout)
  i18n.py               Internationalization (t() function)
  locale/
    de.json             German language file
    en.json             English language file
  models/
    scan_result.py      ScanResult, PageError, enums (response_headers, content_type, last_modified)
    sitemap.py          Sitemap parser + auto-discovery
    history.py          Scan history persistence
    settings.py         Settings persistence (theme, language, concurrency, timeout,
                        console_level, consent, lazy_load, whitelist, headless, preview, ...)
    whitelist.py        Whitelist (wildcard pattern matching)
  widgets/
    results_table.py    ResultsDataTable (right-click context menu, sortable columns) +
                        SearchInputWithHistory filter + auto-scroll
    stats_panel.py      Detail pane: Page / HTTP-Headers (collapsible) / Errors /
                        Warnings / Whitelist / Info Rich-Panels
    preview_panel.py    Screenshot preview via textual-image (TGP/Sixel) or Halfblock
    summary_panel.py    InfoHeader at the top (4 columns: target / config / errors / progress)
  screens/
    error_detail.py     Modal: error details (markup + hover-links + close button)
    top_errors.py       Modal: top 10 errors chart (auto-height + close button)
    history.py          Modal: scan history (select + close buttons)
    whitelist.py        Modal: whitelist viewer (patterns + hit counts)
    settings.py         BaseSettingsScreen: Scanner tab + Language tab + Storage paths tab
  services/
    scanner.py          Playwright scanner (retry, recovery, response headers capture)
    reporter.py         HTML + JSON report generator
    preview_service.py  Playwright sidecar + disk cache for preview screenshots
    image_clipboard.py  Cross-platform image-to-clipboard (Win: pywin32, macOS: osascript,
                        Linux: xclip/wl-copy)
```

Built on [textual-themes](https://github.com/michaelblaess/textual-themes) (36 retro palettes),
[textual-widgets](https://github.com/michaelblaess/textual-widgets) (CrashGuard, LogPanel,
BaseSettingsScreen, AboutScreen, UrlInputScreen, ContextMenuScreen, Splitters, InfoHeader,
ClickableLinksMixin) and [textual-fspicker](https://github.com/davep/textual-fspicker)
(FileOpen dialog).
