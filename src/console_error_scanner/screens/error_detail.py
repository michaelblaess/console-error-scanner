"""Modal-Screen fuer Fehlerdetails."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static
from rich.text import Text

from ..models.scan_result import ErrorType, ScanResult


class ErrorDetailScreen(ModalScreen):
    """Modal-Dialog mit ausfuehrlichen Fehlerdetails einer URL."""

    DEFAULT_CSS = """
    ErrorDetailScreen {
        align: center middle;
    }

    ErrorDetailScreen > Vertical {
        width: 80%;
        max-width: 100;
        height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    ErrorDetailScreen #detail-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: $text;
        margin-bottom: 1;
    }

    ErrorDetailScreen #detail-content {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }

    ErrorDetailScreen #detail-footer {
        height: 1;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen"),
        Binding("q", "close", "Schliessen"),
    ]

    def __init__(self, result: ScanResult, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result = result

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        with Vertical():
            yield Static(f"Fehlerdetails: {self._result.url}", id="detail-title")
            yield Static(self._build_content(), id="detail-content")
            yield Static("ESC / q = Schliessen", id="detail-footer")

    def _build_content(self) -> Text:
        """Erstellt den Detail-Text.

        Returns:
            Formatierter Rich Text mit allen Fehlerdetails.
        """
        result = self._result
        text = Text()

        text.append(f"URL: {result.url}\n", style="bold")
        text.append(f"HTTP Status: {result.http_status_code}\n")
        text.append(f"Ladezeit: {result.load_time_ms}ms\n")
        text.append(f"Retries: {result.retry_count}\n")
        text.append(f"Fehler gesamt: {result.total_error_count}\n\n")

        if not result.errors:
            text.append("Keine Fehler.", style="green")
            return text

        for error in result.errors:
            type_style = {
                ErrorType.CONSOLE_ERROR: "bold red",
                ErrorType.HTTP_404: "bold yellow",
                ErrorType.HTTP_4XX: "bold yellow",
                ErrorType.HTTP_5XX: "bold red",
            }.get(error.error_type, "")
            type_label = {
                ErrorType.CONSOLE_ERROR: "CONSOLE",
                ErrorType.HTTP_404: "HTTP 404",
                ErrorType.HTTP_4XX: "HTTP 4xx",
                ErrorType.HTTP_5XX: "HTTP 5xx",
            }.get(error.error_type, "?")

            text.append(f"[{type_label}] ", style=type_style)
            text.append(f"{error.message}\n")
            if error.source:
                source = error.source
                if error.line_number:
                    source += f":{error.line_number}"
                text.append(f"  Quelle: {source}\n", style="dim")
            text.append("\n")

        return text

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss()
