"""About-Screen fuer Console Error Scanner."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult, RenderResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static

from .. import __author__, __version__, __year__
from ..i18n import t


class AboutContent(Widget):
    """Rendert den About-Inhalt als Rich Text."""

    DEFAULT_CSS = """
    AboutContent {
        height: auto;
        padding: 1 2;
    }
    """

    def render(self) -> RenderResult:
        """Erstellt den About-Text."""
        text = Text()
        text.append(f"v{__version__}", style="bold")
        text.append("  \u00b7  ", style="dim")
        text.append(__author__, style="bold")
        text.append("  \u00b7  ", style="dim")
        text.append(__year__, style="bold")
        text.append("\n\n")

        text.append(f"{t('about.description_1')}\n")
        text.append(f"{t('about.description_2')}\n\n")
        text.append(f"{t('about.input')}\n")
        text.append(f"{t('about.output')}\n\n")

        text.append("\u2500" * 44 + "\n\n", style="dim")

        text.append(f"{t('about.quote')}\n\n", style="italic")
        text.append(f"  \u2014 {t('about.quote_author')}", style="bold")

        return text


class AboutScreen(ModalScreen):
    """Modal-Dialog mit Informationen ueber die Anwendung."""

    DEFAULT_CSS = """
    AboutScreen {
        align: center middle;
    }

    AboutScreen > VerticalScroll {
        width: 60;
        height: 30;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    AboutScreen #about-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: $text;
        margin-bottom: 1;
    }

    AboutScreen #about-footer {
        height: 1;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        with VerticalScroll():
            yield Static(t("about.title"), id="about-title")
            yield AboutContent()
            yield Static(t("about.footer"), id="about-footer")

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss()
