"""Modal-Screen "Diaet-Ratgeber": die dicken Brocken einer Seite.

Zeigt die groessten Einzelressourcen einer gescannten Seite als horizontalen
Balken-Chart - damit man auf einen Blick sieht, was die Seite fett macht.
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
from ..models.scan_result import ScanResult, format_page_size
from ..widgets.bar_chart import render_bars


def _short_name(url: str) -> str:
    """Kuerzt eine URL auf den Dateinamen (ohne Query), max. 48 Zeichen."""
    path = urlparse(url).path
    name = unquote(path.rsplit("/", 1)[-1]) or path or url
    return name if len(name) <= 48 else name[:47] + "…"


class DietAdvisorScreen(ModalScreen[None]):
    """Diaet-Ratgeber: groesste Ressourcen einer Seite als Balken-Chart."""

    DEFAULT_CSS = """
    DietAdvisorScreen {
        align: center middle;
    }

    DietAdvisorScreen > Vertical {
        width: 80%;
        max-width: 110;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    DietAdvisorScreen #diet-title {
        height: auto;
        max-height: 5;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: auto;
        margin-bottom: 1;
        padding: 1 2;
    }

    DietAdvisorScreen #diet-scroll {
        height: 1fr;
    }

    DietAdvisorScreen #diet-content {
        height: auto;
        padding: 1;
    }

    DietAdvisorScreen #diet-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    DietAdvisorScreen #diet-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q,Q", "close", "Close"),
    ]

    def __init__(self, result: ScanResult, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._result = result

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("diet.title", url=self._result.url), id="diet-title")
            with VerticalScroll(id="diet-scroll"):
                yield Static(self._build_content(), id="diet-content")
            with Horizontal(id="diet-buttons"):
                yield Button(t("binding.close"), variant="primary", id="diet-close")

    def _build_content(self) -> Text:
        result = self._result
        text = Text()
        text.append(
            t("diet.subtitle", size=format_page_size(result.page_size_bytes)),
            style="bold",
        )
        text.append("\n\n")

        if not result.resource_sizes:
            text.append(t("diet.none"), style="dim")
            return text

        rows: list[tuple[int, str, str]] = [
            (
                res.size_bytes,
                format_page_size(res.size_bytes),
                f"{(res.resource_type or '?'):<10} {_short_name(res.url)}",
            )
            for res in result.resource_sizes
        ]
        text.append_text(render_bars(rows))
        text.append("\n\n")
        text.append(t("diet.tip"), style="italic dim")
        return text

    @on(Button.Pressed, "#diet-close")
    def _on_close_button(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
