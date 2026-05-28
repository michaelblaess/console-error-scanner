"""Modal-Screen fuer Fehlerdetails."""

from __future__ import annotations

from rich.markup import escape as escape_markup
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..i18n import t
from ..models.scan_result import ErrorType, ScanResult

_TYPE_LABELS: dict[ErrorType, str] = {
    ErrorType.CONSOLE_ERROR: "CONSOLE",
    ErrorType.CONSOLE_WARNING: "WARNING",
    ErrorType.HTTP_404: "HTTP 404",
    ErrorType.HTTP_4XX: "HTTP 4xx",
    ErrorType.HTTP_5XX: "HTTP 5xx",
}

_TYPE_STYLES: dict[ErrorType, str] = {
    ErrorType.CONSOLE_ERROR: "bold red",
    ErrorType.CONSOLE_WARNING: "bold yellow",
    ErrorType.HTTP_404: "bold yellow",
    ErrorType.HTTP_4XX: "bold yellow",
    ErrorType.HTTP_5XX: "bold red",
}


class ErrorDetailScreen(ModalScreen[None]):
    """Modal-Dialog mit ausfuehrlichen Fehlerdetails einer URL."""

    DEFAULT_CSS = """
    ErrorDetailScreen {
        align: center middle;
    }

    ErrorDetailScreen > Vertical {
        width: 80%;
        max-width: 110;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    ErrorDetailScreen #detail-title {
        height: auto;
        max-height: 5;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: auto;
        margin-bottom: 1;
        padding: 1 2;
    }

    ErrorDetailScreen #detail-content {
        height: auto;
        padding: 1;
    }

    ErrorDetailScreen #detail-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    ErrorDetailScreen #detail-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q,Q", "close", "Close"),
    ]

    def __init__(self, result: ScanResult, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result = result

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("error_detail_screen.title", url=self._result.url), id="detail-title")
            content = Static(self._build_markup(), id="detail-content", markup=True)
            yield content
            with Horizontal(id="detail-buttons"):
                yield Button(t("binding.close"), variant="primary", id="detail-close")

    def _link(self, text: str, target: str) -> str:
        """Erzeugt ein Hover-klickbares Markup-Snippet (ueber ClickableLinksMixin)."""
        link_markup = getattr(self.app, "link_markup", None)
        if callable(link_markup):
            return link_markup(escape_markup(text), target)
        return escape_markup(text)

    def _build_markup(self) -> str:
        """Erstellt den Detail-Inhalt als Rich-Markup-String mit Hover-Links."""
        result = self._result
        parts: list[str] = []

        parts.append(f"[bold]URL:[/] {self._link(result.url, result.url)}")
        parts.append(escape_markup(t("error_detail_screen.http_status", code=result.http_status_code)))
        parts.append(escape_markup(t("error_detail_screen.load_time", time=result.load_time_ms)))
        parts.append(escape_markup(t("error_detail_screen.retries", count=result.retry_count)))
        ignored_info = f", {result.ignored_count} ignored" if result.ignored_count > 0 else ""
        parts.append(
            escape_markup(t("error_detail_screen.total_errors", total=result.total_error_count, ignored=ignored_info))
        )
        parts.append("")

        active_errors = [e for e in result.errors if not e.whitelisted]
        ignored_errors = [e for e in result.errors if e.whitelisted]

        if not active_errors and not ignored_errors:
            parts.append(f"[green]{escape_markup(t('error_detail_screen.no_errors'))}[/]")
            return "\n".join(parts)

        for error in active_errors:
            style = _TYPE_STYLES.get(error.error_type, "")
            label = _TYPE_LABELS.get(error.error_type, "?")
            tag = f"[{style}]\\[{label}][/]" if style else f"\\[{label}]"
            parts.append(f"{tag} {escape_markup(error.message)}")
            if error.source:
                source = error.source
                if error.line_number:
                    source += f":{error.line_number}"
                parts.append(
                    f"[dim]{escape_markup(t('error_detail_screen.source', source=''))}[/]{self._link(source, error.source)}"
                )
            parts.append("")

        if ignored_errors:
            parts.append(
                f"[dim underline]{escape_markup(t('error_detail_screen.whitelist_hits', count=len(ignored_errors)))}[/]"
            )
            parts.append("")
            for error in ignored_errors:
                label = _TYPE_LABELS.get(error.error_type, "?")
                parts.append(f"[dim]\\[{label}] {escape_markup(error.message)}[/]")
                parts.append("")

        return "\n".join(parts)

    @on(Button.Pressed, "#detail-close")
    def _on_close_button(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
