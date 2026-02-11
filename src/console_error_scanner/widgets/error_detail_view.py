"""Detail-Ansicht fuer Fehler einer gescannten URL."""

from __future__ import annotations

from rich.text import Text
from textual.app import RenderResult
from textual.widget import Widget

from ..models.scan_result import ErrorType, ScanResult, PageStatus


# Maximale Laenge fuer URLs in der Anzeige
MAX_URL_DISPLAY_LEN = 80


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
        if result.has_errors:
            text.append(
                f"Fehler: {result.console_error_count} Errors, "
                f"{result.console_warning_count} Warns, "
                f"{result.http_404_count} 404, "
                f"{result.http_4xx_count} 4xx, "
                f"{result.http_5xx_count} 5xx\n",
                style="bold",
            )

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

        # Console Errors
        console_errors = [e for e in result.errors if e.error_type == ErrorType.CONSOLE_ERROR]
        if console_errors:
            text.append(f"Console Errors ({len(console_errors)})\n", style="bold red underline")
            text.append("\n")

            for idx, error in enumerate(console_errors, 1):
                text.append(f"  {idx}. ", style="bold red")

                # Fehlermeldung hervorheben - erste Zeile fett
                msg_lines = error.message.split("\n") if error.message else ["(kein Text)"]
                first_line = msg_lines[0]
                if len(first_line) > 120:
                    first_line = f"{first_line[:117]}..."
                text.append(f"{first_line}\n", style="bold white")

                # Restliche Zeilen der Fehlermeldung
                for extra_line in msg_lines[1:3]:
                    truncated = extra_line[:120] + "..." if len(extra_line) > 120 else extra_line
                    text.append(f"     {truncated}\n", style="")
                if len(msg_lines) > 3:
                    text.append(f"     ... ({len(msg_lines) - 3} weitere Zeilen)\n", style="dim")

                # Quelle
                if error.source:
                    source_display = _truncate_url(error.source)
                    source_line = f"     Quelle: {source_display}"
                    if error.line_number:
                        source_line += f":{error.line_number}"
                    text.append(f"{source_line}\n", style="dim cyan")

                text.append("\n")

        # Console Warnings (ohne CSP-Violations)
        console_warnings = [
            e for e in result.errors
            if e.error_type == ErrorType.CONSOLE_WARNING and not e.message.startswith("CSP violation:")
        ]
        if console_warnings:
            text.append(f"Console Warnings ({len(console_warnings)})\n", style="bold yellow underline")
            text.append("\n")

            for idx, error in enumerate(console_warnings, 1):
                text.append(f"  {idx}. ", style="bold yellow")

                msg_lines = error.message.split("\n") if error.message else ["(kein Text)"]
                first_line = msg_lines[0]
                if len(first_line) > 120:
                    first_line = f"{first_line[:117]}..."
                text.append(f"{first_line}\n", style="bold white")

                for extra_line in msg_lines[1:3]:
                    truncated = extra_line[:120] + "..." if len(extra_line) > 120 else extra_line
                    text.append(f"     {truncated}\n", style="")
                if len(msg_lines) > 3:
                    text.append(f"     ... ({len(msg_lines) - 3} weitere Zeilen)\n", style="dim")

                if error.source:
                    source_display = _truncate_url(error.source)
                    source_line = f"     Quelle: {source_display}"
                    if error.line_number:
                        source_line += f":{error.line_number}"
                    text.append(f"{source_line}\n", style="dim cyan")

                text.append("\n")

        # CSP Violations
        csp_violations = [
            e for e in result.errors
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
        http_404 = [e for e in result.errors if e.error_type == ErrorType.HTTP_404]
        if http_404:
            text.append(f"HTTP 404 ({len(http_404)})\n", style="bold yellow underline")
            text.append("\n")

            for idx, error in enumerate(http_404, 1):
                text.append(f"  {idx}. ", style="bold yellow")
                url_display = _truncate_url(error.source or error.message)
                text.append(f"{url_display}\n", style="bold white")
                text.append("\n")

        # HTTP 4xx (ohne 404)
        http_4xx = [e for e in result.errors if e.error_type == ErrorType.HTTP_4XX]
        if http_4xx:
            text.append(f"HTTP 4xx ({len(http_4xx)})\n", style="bold yellow underline")
            text.append("\n")

            for idx, error in enumerate(http_4xx, 1):
                text.append(f"  {idx}. ", style="bold yellow")
                text.append(f"{error.message}\n", style="bold white")
                text.append("\n")

        # HTTP 5xx
        http_5xx = [e for e in result.errors if e.error_type == ErrorType.HTTP_5XX]
        if http_5xx:
            text.append(f"HTTP 5xx ({len(http_5xx)})\n", style="bold red underline")
            text.append("\n")

            for idx, error in enumerate(http_5xx, 1):
                text.append(f"  {idx}. ", style="bold red")
                text.append(f"{error.message}\n", style="bold white")
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
