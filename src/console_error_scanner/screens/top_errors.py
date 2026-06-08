"""Modal-Screen fuer Top-10-Fehler Chart."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from rich.markup import escape as escape_markup
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..i18n import t
from ..models.scan_result import ErrorType, ScanResult

# Maximale Laenge fuer Fehlermeldungen in der Anzeige
MAX_MSG_LEN = 80
# Breite des Balkens
BAR_WIDTH = 40


class TopErrorsScreen(ModalScreen):
    """Modal-Dialog mit Top-10-Fehler als Balkendiagramm."""

    DEFAULT_CSS = """
    TopErrorsScreen {
        align: center middle;
    }

    TopErrorsScreen > VerticalScroll {
        width: 90%;
        max-width: 120;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    TopErrorsScreen #top-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: auto;
        margin-bottom: 1;
    }

    TopErrorsScreen #top-content {
        height: auto;
    }

    TopErrorsScreen #top-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    TopErrorsScreen #top-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, results: list[ScanResult], **kwargs) -> None:
        super().__init__(**kwargs)
        self._results = results

    def _link(self, display: str, target: str) -> Text:
        """Baut einen Hover-klickbaren Link-Text (volle URL als Klickziel).

        Args:
            display:
                Der angezeigte (ggf. gekuerzte) Text.
            target:
                Die vollstaendige URL, die beim Klick geoeffnet wird.

        Returns:
            Ein ``Text`` mit ``@click``-Meta - oder unverlinkt, falls die App
            keinen ``link_markup``-Helfer bereitstellt.
        """
        link_fn = getattr(self.app, "link_markup", None)
        if callable(link_fn):
            return Text.from_markup(link_fn(escape_markup(display), target))
        return Text(display)

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        with VerticalScroll():
            yield Static(t("top_errors.title"), id="top-title")
            yield Static(self._build_chart(), id="top-content")
            with Horizontal(id="top-buttons"):
                yield Button(t("binding.close"), variant="primary", id="top-close")

    @on(Button.Pressed, "#top-close")
    def _on_close_button(self) -> None:
        self.dismiss()

    def _build_chart(self) -> Text:
        """Erstellt das Balkendiagramm der Top-10-Fehler.

        Returns:
            Formatierter Rich Text mit Balkendiagramm.
        """
        text = Text()

        # Alle Fehler sammeln und nach Typ gruppieren
        console_counter: Counter = Counter()
        warning_counter: Counter = Counter()
        http_404_counter: Counter = Counter()
        http_4xx_counter: Counter = Counter()
        http_5xx_counter: Counter = Counter()

        for result in self._results:
            for error in result.errors:
                if error.whitelisted:
                    continue
                if error.error_type == ErrorType.CONSOLE_ERROR:
                    msg = _normalize_message(error.message)
                    console_counter[msg] += 1
                elif error.error_type == ErrorType.CONSOLE_WARNING:
                    msg = _normalize_message(error.message)
                    warning_counter[msg] += 1
                elif error.error_type == ErrorType.HTTP_404:
                    http_404_counter[error.source or error.message] += 1
                elif error.error_type == ErrorType.HTTP_4XX:
                    http_4xx_counter[error.source or error.message] += 1
                elif error.error_type == ErrorType.HTTP_5XX:
                    http_5xx_counter[error.source or error.message] += 1

        # Gesamtzaehler
        total_errors = (
            sum(console_counter.values())
            + sum(warning_counter.values())
            + sum(http_404_counter.values())
            + sum(http_4xx_counter.values())
            + sum(http_5xx_counter.values())
        )

        if total_errors == 0:
            text.append(t("top_errors.no_errors"), style="green bold")
            return text

        text.append(t("top_errors.total", count=total_errors), style="bold")
        pages_with_errors = sum(1 for r in self._results if r.has_issues)
        text.append(f"{t('top_errors.pages', count=pages_with_errors)}\n", style="bold")
        text.append("\n")

        # === Console Errors Top 10 ===
        if console_counter:
            _append_section(text, "Console Errors", console_counter, "red")

        # === Console Warnings Top 10 ===
        if warning_counter:
            _append_section(text, "Console Warnings", warning_counter, "yellow")

        # === HTTP 404 Top 10 === (Eintraege sind URLs -> Hover-Links)
        if http_404_counter:
            _append_section(text, "HTTP 404", http_404_counter, "yellow", link_fn=self._link)

        # === HTTP 4xx Top 10 ===
        if http_4xx_counter:
            _append_section(text, "HTTP 4xx", http_4xx_counter, "yellow", link_fn=self._link)

        # === HTTP 5xx Top 10 ===
        if http_5xx_counter:
            _append_section(text, "HTTP 5xx", http_5xx_counter, "red", link_fn=self._link)

        # === Seiten mit den meisten Fehlern ===
        text.append("\u2500" * 60, style="dim")
        text.append("\n\n")
        text.append(f"{t('top_errors.most_errors')}\n", style="bold cyan underline")
        text.append("\n")
        page_errors = [(r.url, r.total_error_count) for r in self._results if r.has_issues]
        page_errors.sort(key=lambda x: x[1], reverse=True)

        if page_errors:
            max_page_count = page_errors[0][1]
            for rank, (url, count) in enumerate(page_errors[:10], 1):
                label = self._link(_truncate(url, MAX_MSG_LEN), url)
                _append_bar_entry(text, rank, label, count, max_page_count, "cyan")

        return text

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss()


def _append_section(
    text: Text,
    title: str,
    counter: Counter,
    color: str,
    link_fn: Callable[[str, str], Text] | None = None,
) -> None:
    """Fuegt eine Chart-Sektion mit Balkendiagramm hinzu.

    Args:
        text: Rich Text zum Anhaengen.
        title: Titel der Sektion.
        counter: Counter mit Fehlermeldung -> Anzahl.
        color: Farbe der Balken.
        link_fn:
            Optionaler Helfer (display, target) -> klickbarer Text. Gesetzt,
            wenn die Counter-Keys URLs sind (HTTP-Sektionen) - dann wird das
            Label ein Hover-Link mit der vollen URL als Klickziel.
    """
    text.append(f"{title}\n", style=f"bold {color} underline")
    text.append("\n")

    max_count = counter.most_common(1)[0][1] if counter else 1
    for rank, (msg, count) in enumerate(counter.most_common(10), 1):
        display = _truncate(msg, MAX_MSG_LEN)
        label: str | Text = link_fn(display, msg) if link_fn else display
        _append_bar_entry(text, rank, label, count, max_count, color)

    text.append("\n")


def _normalize_message(msg: str) -> str:
    """Normalisiert eine Fehlermeldung fuer Gruppierung.

    Entfernt variable Teile wie URLs mit Parametern, Timestamps etc.
    Behaelt den Kerninhalt fuer die Gruppierung.

    Args:
        msg: Originale Fehlermeldung.

    Returns:
        Normalisierte Version.
    """
    if not msg:
        return t("top_errors.empty")

    # Erste Zeile nehmen
    first_line = msg.split("\n")[0].strip()

    # Sehr lange Meldungen kuerzen
    if len(first_line) > 120:
        first_line = f"{first_line[:117]}..."

    return first_line


def _truncate(text: str, max_len: int) -> str:
    """Kuerzt einen Text auf maximale Laenge.

    Args:
        text: Der zu kuerzende Text.
        max_len: Maximale Laenge.

    Returns:
        Gekuerzter Text.
    """
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3]}..."


def _append_bar_entry(
    text: Text,
    rank: int,
    label: str | Text,
    count: int,
    max_count: int,
    color: str,
) -> None:
    """Fuegt einen Chart-Eintrag hinzu (Label ueber Balken).

    Layout:
      1. Fehlermeldung hier...
         ████████████████████████████ 15x

    Args:
        text: Rich Text zum Anhaengen.
        rank: Rang-Nummer.
        label: Beschreibungstext.
        count: Anzahl.
        max_count: Maximaler Wert (fuer Balkenbreite).
        color: Farbe des Balkens.
    """
    # Zeile 1: Rang + Label (Label kann ein klickbarer Text sein)
    text.append(f"  {rank:2d}. ", style="bold")
    if isinstance(label, Text):
        text.append_text(label)
        text.append("\n")
    else:
        text.append(f"{label}\n", style="")

    # Zeile 2: Eingerueckter Balken + Anzahl
    bar_len = max(1, int(BAR_WIDTH * count / max_count)) if max_count > 0 else 1
    bar = "\u2588" * bar_len
    padding = " " * 6  # Einrueckung passend zum Label
    text.append(f"{padding}{bar}", style=f"bold {color}")
    text.append(f" {count}x\n", style="bold")
