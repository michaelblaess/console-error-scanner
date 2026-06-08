"""Modal-Screen "Scan-Zusammenfassung": Site-Score + Findings + Big Fische.

Wird am Ende eines Scans angezeigt: ein Gesamtscore (0-100 %), eine kurze
Findings-Uebersicht und die groessten Seiten/Ressourcen als Balken-Chart.
"""

from __future__ import annotations

from urllib.parse import unquote, urlparse

from rich.markup import escape as escape_markup
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import MouseMove
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


class _SummaryContent(Static):
    """Inhalts-Static der Zusammenfassung mit Hover-Tooltips pro Zeile.

    Textual kennt keine Tooltips pro Text-Span - ``tooltip`` gilt immer fuer das
    ganze Widget. Damit die abgekuerzten ("...") Links trotzdem die volle URL
    zeigen, wird die Zeile unter dem Cursor ueber ``on_mouse_move`` ermittelt und
    der Widget-Tooltip auf die volle URL dieser Zeile gesetzt (oder geleert).
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        # Zeilenindex (0-basiert im gerenderten Text) -> volle URL.
        self.line_urls: dict[int, str] = {}

    def on_mouse_move(self, event: MouseMove) -> None:
        # event.offset.y ist relativ zum Widget inkl. Padding -> Padding-Top
        # abziehen, um auf den Textzeilen-Index zu kommen.
        pad_top = self.styles.padding.top if self.styles.padding else 0
        url = self.line_urls.get(event.offset.y - pad_top)
        self.tooltip = url or None


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
        /* Auf Inhaltshoehe schrumpfen (kein 1fr - das fuellt sonst den ganzen
           verfuegbaren Platz und draengt den Button mit grosser Luecke nach
           unten). max-height: 90% kappt bei langem Inhalt -> der Bereich
           scrollt; bei kurzem Inhalt sitzt der (unten angedockte) Button direkt
           darunter, ohne Luecke. */
        height: auto;
        max-height: 90%;
    }

    ScanSummaryScreen #summary-content {
        height: auto;
        padding: 1;
    }

    ScanSummaryScreen #summary-buttons {
        /* Unten angedockt: bleibt bei langem (scrollendem) Inhalt immer sichtbar
           und sitzt bei kurzem Inhalt direkt unter dem Scroll-Bereich. */
        dock: bottom;
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
        # Zeilenindex -> volle URL, wird in _build_content befuellt.
        self._line_urls: dict[int, str] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("summary.title"), id="summary-title")
            with VerticalScroll(id="summary-scroll"):
                content = _SummaryContent(self._build_content(), id="summary-content")
                content.line_urls = self._line_urls
                yield content
            with Horizontal(id="summary-buttons"):
                yield Button(t("binding.close"), variant="primary", id="summary-close")

    def _link_path(self, display: str, target: str) -> Text:
        """Baut einen Hover-klickbaren Pfad-Text.

        Args:
            display:
                Der angezeigte (ggf. gekuerzte) Pfad.
            target:
                Die vollstaendige URL, die beim Klick geoeffnet wird.

        Returns:
            Ein ``Text`` mit ``@click``-Meta - oder unverlinkt (dim), falls die
            App keinen ``link_markup``-Helfer bereitstellt.
        """
        link_fn = getattr(self.app, "link_markup", None)
        if callable(link_fn):
            return Text.from_markup(link_fn(escape_markup(display), target))
        return Text(display, style="dim")

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
            # Erste Bar-Zeile liegt auf dem aktuellen Zeilenindex (= Anzahl der
            # bisher abgeschlossenen Zeilen). Jede Bar-Zeile -> eine URL.
            start = text.plain.count("\n")
            for i, p in enumerate(s.biggest_pages):
                self._line_urls[start + i] = p.url
            rows: list[tuple[int, str, str | Text]] = [
                (
                    p.page_size_bytes,
                    format_page_size(p.page_size_bytes),
                    self._link_path(_short_url(p.url), p.url),
                )
                for p in s.biggest_pages
            ]
            text.append_text(render_bars(rows, bar_style="magenta"))
            text.append("\n\n")

        # Big Fische (groesste Einzelressourcen).
        if s.biggest_resources:
            text.append(t("summary.big_fish"), style="bold underline")
            text.append("\n")
            start = text.plain.count("\n")
            for i, res in enumerate(s.biggest_resources):
                self._line_urls[start + i] = res.url
            res_rows: list[tuple[int, str, str | Text]] = []
            for res in s.biggest_resources:
                label = Text(f"{(res.resource_type or '?'):<10} ", style="dim")
                label.append_text(self._link_path(_short_url(res.url), res.url))
                res_rows.append((res.size_bytes, format_page_size(res.size_bytes), label))
            text.append_text(render_bars(res_rows, bar_style="cyan"))

        return text

    @on(Button.Pressed, "#summary-close")
    def _on_close_button(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
