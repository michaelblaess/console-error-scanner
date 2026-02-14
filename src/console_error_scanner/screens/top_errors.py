"""Modal-Screen fuer Top-10-Fehler Chart."""

from __future__ import annotations

from collections import Counter

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static
from rich.text import Text

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
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    TopErrorsScreen #top-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: $text;
        margin-bottom: 1;
    }

    TopErrorsScreen #top-footer {
        height: 1;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Schliessen"),
        Binding("q", "close", "Schliessen"),
    ]

    def __init__(self, results: list[ScanResult], **kwargs) -> None:
        super().__init__(**kwargs)
        self._results = results

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        with VerticalScroll():
            yield Static("Top 10 Fehler", id="top-title")
            yield Static(self._build_chart(), id="top-content")
            yield Static("ESC / q = Schliessen", id="top-footer")

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
            sum(console_counter.values()) + sum(warning_counter.values())
            + sum(http_404_counter.values()) + sum(http_4xx_counter.values())
            + sum(http_5xx_counter.values())
        )

        if total_errors == 0:
            text.append("Keine Fehler gefunden.", style="green bold")
            return text

        text.append(f"Gesamt: {total_errors} Fehler auf ", style="bold")
        pages_with_errors = sum(1 for r in self._results if r.has_issues)
        text.append(f"{pages_with_errors} Seiten\n", style="bold")
        text.append("\n")

        # === Console Errors Top 10 ===
        if console_counter:
            _append_section(text, "Console Errors", console_counter, "red")

        # === Console Warnings Top 10 ===
        if warning_counter:
            _append_section(text, "Console Warnings", warning_counter, "yellow")

        # === HTTP 404 Top 10 ===
        if http_404_counter:
            _append_section(text, "HTTP 404", http_404_counter, "yellow")

        # === HTTP 4xx Top 10 ===
        if http_4xx_counter:
            _append_section(text, "HTTP 4xx", http_4xx_counter, "yellow")

        # === HTTP 5xx Top 10 ===
        if http_5xx_counter:
            _append_section(text, "HTTP 5xx", http_5xx_counter, "red")

        # === Seiten mit den meisten Fehlern ===
        text.append("\u2500" * 60, style="dim")
        text.append("\n\n")
        text.append("Seiten mit den meisten Fehlern\n", style="bold cyan underline")
        text.append("\n")
        page_errors = [(r.url, r.total_error_count) for r in self._results if r.has_issues]
        page_errors.sort(key=lambda x: x[1], reverse=True)

        if page_errors:
            max_page_count = page_errors[0][1]
            for rank, (url, count) in enumerate(page_errors[:10], 1):
                display = _truncate(url, MAX_MSG_LEN)
                _append_bar_entry(text, rank, display, count, max_page_count, "cyan")

        return text

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss()


def _append_section(text: Text, title: str, counter: Counter, color: str) -> None:
    """Fuegt eine Chart-Sektion mit Balkendiagramm hinzu.

    Args:
        text: Rich Text zum Anhaengen.
        title: Titel der Sektion.
        counter: Counter mit Fehlermeldung -> Anzahl.
        color: Farbe der Balken.
    """
    text.append(f"{title}\n", style=f"bold {color} underline")
    text.append("\n")

    max_count = counter.most_common(1)[0][1] if counter else 1
    for rank, (msg, count) in enumerate(counter.most_common(10), 1):
        display = _truncate(msg, MAX_MSG_LEN)
        _append_bar_entry(text, rank, display, count, max_count, color)

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
        return "(leer)"

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
    return f"{text[:max_len - 3]}..."


def _append_bar_entry(
    text: Text,
    rank: int,
    label: str,
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
    # Zeile 1: Rang + Label
    text.append(f"  {rank:2d}. ", style="bold")
    text.append(f"{label}\n", style="")

    # Zeile 2: Eingerueckter Balken + Anzahl
    bar_len = max(1, int(BAR_WIDTH * count / max_count)) if max_count > 0 else 1
    bar = "\u2588" * bar_len
    padding = " " * 6  # Einrueckung passend zum Label
    text.append(f"{padding}{bar}", style=f"bold {color}")
    text.append(f" {count}x\n", style="bold")
