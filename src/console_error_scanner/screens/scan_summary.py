"""Modal-Screen "Scan-Zusammenfassung": Site-Score + Findings + Big Fische.

Wird am Ende eines Scans angezeigt: ein Gesamtscore (0-100 %), eine kurze
Findings-Uebersicht und die groessten Seiten/Ressourcen als Balken-Chart.
"""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..i18n import t
from ..models.scan_result import format_page_size
from ..services.site_score import SiteScore
from ..widgets.bar_chart import render_bars


def _score_style(score: int) -> str:
    """Farbstil zum Score (gruen/gelb/rot)."""
    if score >= 75:
        return "bold green"
    if score >= 45:
        return "bold yellow"
    return "bold red"


def _short_url(url: str) -> str:
    """Kuerzt eine URL auf Pfad (ohne Host), max. 52 Zeichen."""
    parsed = urlparse(url)
    path = unquote(parsed.path) or "/"
    return path if len(path) <= 52 else path[:51] + "…"


class ScanSummaryScreen(ModalScreen[None]):
    """Zeigt Site-Score, Findings und die Big Fische nach einem Scan."""

    DEFAULT_CSS = """
    ScanSummaryScreen {
        align: center middle;
    }

    ScanSummaryScreen > Vertical {
        width: 80%;
        max-width: 110;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    ScanSummaryScreen #summary-title {
        height: auto;
        max-height: 5;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: auto;
        margin-bottom: 1;
        padding: 1 2;
    }

    ScanSummaryScreen #summary-scroll {
        height: 1fr;
    }

    ScanSummaryScreen #summary-content {
        height: auto;
        padding: 1;
    }

    ScanSummaryScreen #summary-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    ScanSummaryScreen #summary-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q,Q", "close", "Close"),
    ]

    def __init__(self, score: SiteScore, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._score = score

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("summary.title"), id="summary-title")
            with VerticalScroll(id="summary-scroll"):
                yield Static(self._build_content(), id="summary-content")
            with Horizontal(id="summary-buttons"):
                yield Button(t("binding.close"), variant="primary", id="summary-close")

    def _build_content(self) -> Text:
        s = self._score
        text = Text()

        # Grosse Score-Zeile.
        text.append(t("summary.score_label") + " ", style="bold")
        text.append(f"{s.score} %", style=_score_style(s.score))
        text.append(f"  ({s.grade})", style=_score_style(s.score))
        text.append("\n")
        text.append(
            t(
                "summary.score_breakdown",
                err=s.error_score,
                err_w=s.error_weight,
                size=s.size_score,
                size_w=100 - s.error_weight,
            ),
            style="dim",
        )
        text.append("\n\n")

        # Findings.
        text.append(t("summary.findings"), style="bold underline")
        text.append("\n")
        text.append(t("summary.pages", total=s.total_pages, clean=s.clean_pages, err=s.pages_with_errors))
        text.append("\n")
        text.append(t("summary.errors", errors=s.total_errors, warnings=s.total_warnings))
        text.append("\n")
        text.append(t("summary.avg_size", size=format_page_size(s.avg_page_size_bytes)))
        text.append("\n\n")

        # Groesste Seiten.
        if s.biggest_pages:
            text.append(t("summary.biggest_pages"), style="bold underline")
            text.append("\n")
            rows = [(p.page_size_bytes, format_page_size(p.page_size_bytes), _short_url(p.url)) for p in s.biggest_pages]
            text.append_text(render_bars(rows, bar_style="magenta"))
            text.append("\n\n")

        # Big Fische (groesste Einzelressourcen).
        if s.biggest_resources:
            text.append(t("summary.big_fish"), style="bold underline")
            text.append("\n")
            rows = [
                (
                    res.size_bytes,
                    format_page_size(res.size_bytes),
                    f"{(res.resource_type or '?'):<10} {_short_url(res.url)}",
                )
                for res in s.biggest_resources
            ]
            text.append_text(render_bars(rows, bar_style="cyan"))

        return text

    @on(Button.Pressed, "#summary-close")
    def _on_close_button(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
