"""Detail-Ansicht fuer Fehler einer gescannten URL."""

from __future__ import annotations

import re

from rich.text import Text
from textual.app import RenderResult
from textual.widget import Widget

from ..models.scan_result import ErrorType, ScanResult, PageStatus


# Maximale Laenge fuer URLs in der Anzeige
MAX_URL_DISPLAY_LEN = 80
# Maximale Laenge fuer gekuerzte Pfade in Stack-Traces
MAX_PATH_DISPLAY_LEN = 60


class ErrorDetailView(Widget):
    """Zeigt die Fehlerdetails einer ausgewaehlten URL."""

    DEFAULT_CSS = """
    ErrorDetailView {
        height: 1fr;
        padding: 1 2;
        background: $surface;
        border-left: solid $accent;
        overflow-y: scroll;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result: ScanResult | None = None

    def render(self) -> RenderResult:
        """Rendert die Fehlerdetails."""
        if not self._result:
            return Text("Keine URL ausgewaehlt.\n\nWaehle eine URL in der Tabelle aus.", style="dim italic")

        result = self._result
        text = Text()

        # URL-Header
        text.append("URL\n", style="bold underline")
        text.append(f"{result.url}\n\n", style="bold cyan")

        # Status-Zeile
        text.append("Status: ", style="bold")
        status_style = {
            PageStatus.OK: "bold green",
            PageStatus.WARNING: "bold yellow",
            PageStatus.ERROR: "bold red",
            PageStatus.TIMEOUT: "bold yellow",
            PageStatus.SCANNING: "bold cyan",
            PageStatus.PENDING: "dim",
        }.get(result.status, "")
        text.append(f"{result.status_icon}", style=status_style)

        if result.http_status_code > 0:
            text.append(f"  |  HTTP {result.http_status_code}")

        if result.load_time_ms > 0:
            load_s = result.load_time_ms / 1000
            text.append(f"  |  {load_s:.1f}s")

        if result.retry_count > 0:
            text.append(f"  |  {result.retry_count} Retries", style="yellow")

        text.append("\n")

        # Fehler-Zusammenfassung
        if result.has_errors or result.ignored_count > 0:
            summary_parts = (
                f"Fehler: {result.console_error_count} Errors, "
                f"{result.console_warning_count} Warns, "
                f"{result.http_404_count} 404, "
                f"{result.http_4xx_count} 4xx, "
                f"{result.http_5xx_count} 5xx"
            )
            if result.ignored_count > 0:
                summary_parts += f", {result.ignored_count} ignored"
            text.append(f"{summary_parts}\n", style="bold")

        text.append("\n")

        # Keine Fehler?
        if not result.errors:
            if result.status == PageStatus.OK:
                text.append("Keine Fehler gefunden.", style="green")
            elif result.status == PageStatus.SCANNING:
                text.append("Scan laeuft...", style="cyan")
            elif result.status == PageStatus.PENDING:
                text.append("Noch nicht gescannt.", style="dim")
            return text

        # Nur aktive (nicht-whitelisted) Fehler in den Sektionen anzeigen
        active_errors = [e for e in result.errors if not e.whitelisted]

        # Console Errors
        console_errors = [e for e in active_errors if e.error_type == ErrorType.CONSOLE_ERROR]
        if console_errors:
            text.append(f"Console Errors ({len(console_errors)})\n", style="bold red underline")
            text.append("\n")

            for idx, error in enumerate(console_errors, 1):
                text.append(f"  {idx}. ", style="bold red")
                _append_error_message(text, error)
                text.append("\n")

        # Console Warnings (ohne CSP-Violations)
        console_warnings = [
            e for e in active_errors
            if e.error_type == ErrorType.CONSOLE_WARNING and not e.message.startswith("CSP violation:")
        ]
        if console_warnings:
            text.append(f"Console Warnings ({len(console_warnings)})\n", style="bold yellow underline")
            text.append("\n")

            for idx, error in enumerate(console_warnings, 1):
                text.append(f"  {idx}. ", style="bold yellow")
                _append_error_message(text, error)
                text.append("\n")

        # CSP Violations
        csp_violations = [
            e for e in active_errors
            if e.error_type == ErrorType.CONSOLE_WARNING and e.message.startswith("CSP violation:")
        ]
        if csp_violations:
            text.append(f"CSP Violations ({len(csp_violations)})\n", style="bold magenta underline")
            text.append("\n")

            for idx, error in enumerate(csp_violations, 1):
                text.append(f"  {idx}. ", style="bold magenta")
                msg = error.message
                if len(msg) > 120:
                    msg = f"{msg[:117]}..."
                text.append(f"{msg}\n", style="bold white")
                text.append("\n")

        # HTTP 404
        http_404 = [e for e in active_errors if e.error_type == ErrorType.HTTP_404]
        if http_404:
            text.append(f"HTTP 404 ({len(http_404)})\n", style="bold yellow underline")
            text.append("\n")

            for idx, error in enumerate(http_404, 1):
                text.append(f"  {idx}. ", style="bold yellow")
                url_display = _truncate_url(error.source or error.message)
                text.append(f"{url_display}\n", style="bold white")
                text.append("\n")

        # HTTP 4xx (ohne 404)
        http_4xx = [e for e in active_errors if e.error_type == ErrorType.HTTP_4XX]
        if http_4xx:
            text.append(f"HTTP 4xx ({len(http_4xx)})\n", style="bold yellow underline")
            text.append("\n")

            for idx, error in enumerate(http_4xx, 1):
                text.append(f"  {idx}. ", style="bold yellow")
                text.append(f"{error.message}\n", style="bold white")
                text.append("\n")

        # HTTP 5xx
        http_5xx = [e for e in active_errors if e.error_type == ErrorType.HTTP_5XX]
        if http_5xx:
            text.append(f"HTTP 5xx ({len(http_5xx)})\n", style="bold red underline")
            text.append("\n")

            for idx, error in enumerate(http_5xx, 1):
                text.append(f"  {idx}. ", style="bold red")
                text.append(f"{error.message}\n", style="bold white")
                text.append("\n")

        # Whitelist-Treffer (gedimmt, am Ende)
        whitelisted = [e for e in result.errors if e.whitelisted]
        if whitelisted:
            text.append(f"Whitelist-Treffer ({len(whitelisted)})\n", style="dim underline")
            text.append("\n")

            type_labels = {
                ErrorType.CONSOLE_ERROR: "Console",
                ErrorType.CONSOLE_WARNING: "Warning",
                ErrorType.HTTP_404: "HTTP 404",
                ErrorType.HTTP_4XX: "HTTP 4xx",
                ErrorType.HTTP_5XX: "HTTP 5xx",
            }

            for idx, error in enumerate(whitelisted, 1):
                label = type_labels.get(error.error_type, error.error_type.value)
                msg = error.message
                if len(msg) > 100:
                    msg = f"{msg[:97]}..."
                text.append(f"  {idx}. ", style="dim")
                text.append(f"[{label}] ", style="dim")
                text.append(f"{msg}\n", style="dim")

            text.append("\n")

        return text

    def show_result(self, result: ScanResult) -> None:
        """Zeigt die Details eines Scan-Ergebnisses.

        Args:
            result: Das anzuzeigende ScanResult.
        """
        self._result = result
        self.refresh()

    def clear(self) -> None:
        """Leert die Detail-Ansicht."""
        self._result = None
        self.refresh()


def _append_error_message(text: Text, error) -> None:
    """Haengt eine formatierte Fehlermeldung mit Stack-Trace an.

    Erste Zeile wird fett/weiss dargestellt (die eigentliche Fehlermeldung).
    Stack-Trace-Zeilen (at ...) werden gedimmt und URLs darin gekuerzt.

    Args:
        text: Rich Text zum Anhaengen.
        error: PageError mit message und source.
    """
    msg_lines = error.message.split("\n") if error.message else ["(kein Text)"]

    # Erste Zeile: eigentliche Fehlermeldung (fett)
    first_line = msg_lines[0]
    if len(first_line) > 120:
        first_line = f"{first_line[:117]}..."
    text.append(f"{first_line}\n", style="bold white")

    # Restliche Zeilen: Stack-Trace (gedimmt, URLs gekuerzt)
    for extra_line in msg_lines[1:4]:
        shortened = _shorten_stack_line(extra_line)
        text.append(f"       {shortened}\n", style="dim")
    if len(msg_lines) > 4:
        text.append(f"       ... ({len(msg_lines) - 4} weitere Zeilen)\n", style="dim")

    # Quelle
    if error.source:
        source_display = _shorten_url(error.source)
        source_line = f"     Quelle: {source_display}"
        if error.line_number:
            source_line += f":{error.line_number}"
        text.append(f"{source_line}\n", style="dim cyan")


# Regex: erkennt URLs in Stack-Trace-Zeilen (https://... oder http://...)
_URL_PATTERN = re.compile(r"https?://[^\s\)]+")


def _shorten_stack_line(line: str) -> str:
    """Kuerzt URLs in einer Stack-Trace-Zeile.

    Ersetzt lange URLs durch .../letzter-pfad-teil und behaelt den Kontext
    (z.B. 'at k (...)') bei.

    Args:
        line: Eine Zeile aus einem JavaScript Stack-Trace.

    Returns:
        Gekuerzte Zeile.
    """
    line = line.strip()
    if not line:
        return line

    def replace_url(match: re.Match) -> str:
        return _shorten_url(match.group(0))

    shortened = _URL_PATTERN.sub(replace_url, line)

    if len(shortened) > 90:
        shortened = f"{shortened[:87]}..."

    return shortened


def _shorten_url(url: str) -> str:
    """Kuerzt eine URL auf die letzten 2 Pfad-Segmente.

    Beispiel:
        https://www.example.com/Frontend-Assembly/.../Scripts/CustomSingleWidget/FrontendView.js:12
        -> .../CustomSingleWidget/FrontendView.js:12

    Args:
        url: Die zu kuerzende URL.

    Returns:
        Gekuerzte URL.
    """
    if len(url) <= MAX_PATH_DISPLAY_LEN:
        return url

    # Query/Fragment entfernen fuer saubere Pfad-Analyse
    clean = url.split("?")[0].split("#")[0]

    # Protokoll + Domain entfernen
    path_start = clean.find("//")
    if path_start >= 0:
        after_protocol = clean[path_start + 2:]
        slash_pos = after_protocol.find("/")
        if slash_pos >= 0:
            path = after_protocol[slash_pos:]
        else:
            path = ""
    else:
        path = clean

    if not path or path == "/":
        return _truncate_url(url)

    # Letzte 2 Pfad-Segmente behalten
    segments = [s for s in path.split("/") if s]
    if len(segments) <= 2:
        return _truncate_url(url)

    # Zeilennummer (nach letztem :) erhalten falls vorhanden
    last_segment = segments[-1]
    suffix = ""
    # Zeile:Spalte Pattern (z.B. file.js:12:5)
    colon_match = re.search(r"(:\d+(?::\d+)?)$", url)
    if colon_match:
        suffix = colon_match.group(1)
        if last_segment.endswith(suffix):
            last_segment = last_segment[:-len(suffix)]

    short = f".../{'/'.join(segments[-2:-1])}/{last_segment}{suffix}"

    if len(short) > MAX_PATH_DISPLAY_LEN:
        short = f".../{last_segment}{suffix}"

    return short


def _truncate_url(url: str, max_len: int = MAX_URL_DISPLAY_LEN) -> str:
    """Kuerzt eine URL fuer die Anzeige.

    Args:
        url: Die zu kuerzende URL.
        max_len: Maximale Laenge.

    Returns:
        Gekuerzte URL mit ... in der Mitte.
    """
    if len(url) <= max_len:
        return url

    # Behalte Anfang und Ende
    keep = (max_len - 3) // 2
    return f"{url[:keep]}...{url[-keep:]}"
