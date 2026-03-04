"""DataTable-Widget fuer Scan-Ergebnisse."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static
from textual.message import Message
from rich.text import Text

from ..models.scan_result import ScanResult, PageStatus, format_page_size


class ResultsTable(Vertical):
    """Widget mit filterbarer DataTable fuer Scan-Ergebnisse."""

    DEFAULT_CSS = """
    ResultsTable {
        height: 1fr;
    }

    ResultsTable #filter-bar {
        dock: top;
        height: 3;
        padding: 0 1;
    }

    ResultsTable #results-count {
        dock: top;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    ResultsTable DataTable {
        height: 1fr;
    }
    """

    filter_text: reactive[str] = reactive("")

    class ResultSelected(Message):
        """Wird gesendet wenn ein Ergebnis ausgewaehlt wird (Enter/Doppelklick)."""

        def __init__(self, result: ScanResult) -> None:
            super().__init__()
            self.result = result

    class ResultHighlighted(Message):
        """Wird gesendet wenn der Cursor auf ein Ergebnis bewegt wird."""

        def __init__(self, result: ScanResult) -> None:
            super().__init__()
            self.result = result

    # Spinner-Frames fuer SCANNING-Status
    SPINNER_FRAMES = [">  ", ">> ", ">>>", " >>", "  >", "   "]

    # Tasten bei denen Auto-Scroll deaktiviert wird (manuelle Navigation)
    _NAV_KEYS = {"up", "down", "pageup", "pagedown", "home", "end"}

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._results: list[ScanResult] = []
        self._filtered: list[ScanResult] = []
        self._col_keys: list = []
        self._show_only_errors: bool = False
        self._spinner_frame: int = 0
        self._spinner_timer = None
        self._auto_scroll: bool = True
        self._auto_scroll_row: int = -1

    def compose(self) -> ComposeResult:
        """Erstellt die Kind-Widgets."""
        yield Input(placeholder="Filter (URL, Status...)", id="filter-bar")
        yield Static("", id="results-count")
        yield DataTable(id="results-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Initialisiert die Tabellenspalten und startet den Spinner-Timer."""
        table = self.query_one("#results-data", DataTable)
        self._col_keys = table.add_columns(
            "#", "Status", "URL", "HTTP", "Zeit", "Size",
            "Errors", "Warns", "404", "4xx", "5xx", "Ignored",
        )
        self._spinner_timer = self.set_interval(0.3, self._tick_spinner)

    def _tick_spinner(self) -> None:
        """Aktualisiert den Spinner-Frame fuer SCANNING-Zeilen in-place."""
        has_scanning = any(r.status == PageStatus.SCANNING for r in self._filtered)
        if not has_scanning:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        table = self.query_one("#results-data", DataTable)
        for idx, result in enumerate(self._filtered):
            if result.status == PageStatus.SCANNING:
                table.update_cell(
                    str(idx), self._col_keys[1], self._styled_status(result),
                )

    def load_results(self, results: list[ScanResult]) -> None:
        """Laedt Ergebnisse in die Tabelle.

        Setzt Auto-Scroll zurueck, damit beim naechsten Scan
        automatisch zur aktuellen Zeile gescrollt wird.

        Args:
            results: Liste der ScanResults.
        """
        self._results = results
        self._auto_scroll = True
        self._auto_scroll_row = -1
        self._apply_filter()

    def update_result(self, result: ScanResult) -> None:
        """Aktualisiert ein einzelnes Ergebnis in der Tabelle.

        Aktualisiert Zellen in-place (kein clear/rebuild), damit die
        Scroll-Position erhalten bleibt.  Bei aktivem Filter wird
        ein vollstaendiger Rebuild durchgefuehrt falls sich die
        Tabellenstruktur aendern koennte.

        Args:
            result: Das aktualisierte ScanResult.
        """
        if self._show_only_errors or self.filter_text:
            # Filter aktiv - Struktur koennte sich aendern
            self._rebuild_filtered()
            if self._auto_scroll:
                self._scroll_to_result(result)
            self._refresh_table()
            return

        # Kein Filter - Zellen in-place aktualisieren (kein clear/rebuild)
        try:
            idx = self._filtered.index(result)
        except ValueError:
            return

        table = self.query_one("#results-data", DataTable)
        self._update_row_cells(table, idx, result)

        if self._auto_scroll:
            if idx >= self._auto_scroll_row:
                self._auto_scroll_row = idx
            table.move_cursor(row=self._auto_scroll_row)

    def _update_row_cells(self, table: DataTable, idx: int, result: ScanResult) -> None:
        """Aktualisiert alle Zellen einer Zeile in-place.

        Args:
            table: Die DataTable-Instanz.
            idx: Zeilen-Index in der gefilterten Liste.
            result: Das aktualisierte ScanResult.
        """
        row_key = str(idx)
        status_text = self._styled_status(result)
        scanned = result.status not in (PageStatus.PENDING, PageStatus.SCANNING)

        if scanned:
            errors_text = _colored_count(result.console_error_count, "bold red")
            warns_text = _colored_count(result.console_warning_count, "bold yellow")
            http_404_text = _colored_count(result.http_404_count, "bold yellow")
            http_4xx_text = _colored_count(result.http_4xx_count, "bold yellow")
            http_5xx_text = _colored_count(result.http_5xx_count, "bold red")
            ignored_text = (
                Text(str(result.ignored_count), style="dim")
                if result.ignored_count > 0
                else Text("0", style="dim")
            )
        else:
            errors_text = Text("-", style="dim")
            warns_text = Text("-", style="dim")
            http_404_text = Text("-", style="dim")
            http_4xx_text = Text("-", style="dim")
            http_5xx_text = Text("-", style="dim")
            ignored_text = Text("-", style="dim")

        http_code_str = str(result.http_status_code) if result.http_status_code > 0 else "-"
        time_str = f"{result.load_time_ms / 1000:.1f}s" if result.load_time_ms > 0 else "-"
        size_str = format_page_size(result.page_size_bytes) if scanned else "-"

        table.update_cell(row_key, self._col_keys[1], status_text)
        table.update_cell(row_key, self._col_keys[3], http_code_str)
        table.update_cell(row_key, self._col_keys[4], time_str)
        table.update_cell(row_key, self._col_keys[5], size_str)
        table.update_cell(row_key, self._col_keys[6], errors_text)
        table.update_cell(row_key, self._col_keys[7], warns_text)
        table.update_cell(row_key, self._col_keys[8], http_404_text)
        table.update_cell(row_key, self._col_keys[9], http_4xx_text)
        table.update_cell(row_key, self._col_keys[10], http_5xx_text)
        table.update_cell(row_key, self._col_keys[11], ignored_text)

    def _scroll_to_result(self, result: ScanResult) -> None:
        """Merkt sich die Ziel-Zeile fuer Auto-Scroll.

        Bei mehreren parallelen Threads wird nur vorwaerts gescrollt,
        damit der Cursor nicht zwischen aktiven Threads hin- und herspringt.

        Args:
            result: Das ScanResult zu dem gescrollt werden soll.
        """
        try:
            row = self._filtered.index(result)
            if row >= self._auto_scroll_row:
                self._auto_scroll_row = row
        except ValueError:
            pass

    def _rebuild_filtered(self) -> None:
        """Baut die gefilterte Liste neu auf ohne Tabellen-Refresh."""
        search = self.filter_text.lower()

        self._filtered = []
        for r in self._results:
            if self._show_only_errors and not r.has_issues:
                continue
            if search and search not in r.url.lower():
                continue
            self._filtered.append(r)

    def _apply_filter(self) -> None:
        """Wendet den aktuellen Filter an und aktualisiert die Tabelle."""
        self._rebuild_filtered()
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Baut die DataTable komplett neu auf (clear + rebuild).

        Wird nur bei strukturellen Aenderungen verwendet (load_results,
        Filter-Wechsel).  Waehrend des Scannens nutzt update_result()
        stattdessen _update_row_cells() fuer in-place Updates.
        """
        table = self.query_one("#results-data", DataTable)
        saved_row = table.cursor_row
        table.clear()

        for idx, result in enumerate(self._filtered):
            status_text = self._styled_status(result)

            # Fehler-Zaehler nur anzeigen wenn gescannt
            scanned = result.status not in (PageStatus.PENDING, PageStatus.SCANNING)

            if scanned:
                errors_text = _colored_count(result.console_error_count, "bold red")
                warns_text = _colored_count(result.console_warning_count, "bold yellow")
                http_404_text = _colored_count(result.http_404_count, "bold yellow")
                http_4xx_text = _colored_count(result.http_4xx_count, "bold yellow")
                http_5xx_text = _colored_count(result.http_5xx_count, "bold red")
                ignored_text = Text(str(result.ignored_count), style="dim") if result.ignored_count > 0 else Text("0", style="dim")
            else:
                errors_text = Text("-", style="dim")
                warns_text = Text("-", style="dim")
                http_404_text = Text("-", style="dim")
                http_4xx_text = Text("-", style="dim")
                http_5xx_text = Text("-", style="dim")
                ignored_text = Text("-", style="dim")

            http_code_str = str(result.http_status_code) if result.http_status_code > 0 else "-"
            time_str = f"{result.load_time_ms / 1000:.1f}s" if result.load_time_ms > 0 else "-"
            size_str = format_page_size(result.page_size_bytes) if scanned else "-"

            table.add_row(
                str(idx + 1),
                status_text,
                result.url,
                http_code_str,
                time_str,
                size_str,
                errors_text,
                warns_text,
                http_404_text,
                http_4xx_text,
                http_5xx_text,
                ignored_text,
                key=str(idx),
            )

        # Cursor wiederherstellen
        if self._auto_scroll and 0 <= self._auto_scroll_row < len(self._filtered):
            target_row = self._auto_scroll_row
        elif saved_row >= 0 and len(self._filtered) > 0:
            target_row = min(saved_row, len(self._filtered) - 1)
        else:
            target_row = -1

        if target_row >= 0:
            table.move_cursor(row=target_row)

        count_label = self.query_one("#results-count", Static)
        total = len(self._results)
        shown = len(self._filtered)
        if total == shown:
            count_label.update(f" {total} URLs")
        else:
            count_label.update(f" {shown} von {total} URLs (gefiltert)")

    def _styled_status(self, result: ScanResult) -> Text:
        """Erstellt farbcodierten Status-Text.

        Args:
            result: ScanResult mit Status-Info.

        Returns:
            Farbcodierter Rich Text.
        """
        if result.status == PageStatus.SCANNING:
            frame = self.SPINNER_FRAMES[self._spinner_frame % len(self.SPINNER_FRAMES)]
            return Text(frame, style="bold cyan")

        # Nur whitelisted Errors → IGN (gelb)
        if result.has_only_ignored_errors:
            return Text("IGN", style="bold yellow")

        styles = {
            PageStatus.PENDING: ("...", "dim"),
            PageStatus.OK: ("OK", "bold green"),
            PageStatus.WARNING: ("WARN", "bold yellow"),
            PageStatus.ERROR: ("ERR", "bold red"),
            PageStatus.TIMEOUT: ("T/O", "bold yellow"),
        }
        icon, style = styles.get(result.status, ("?", ""))
        return Text(icon, style=style)

    def on_key(self, event) -> None:
        """Deaktiviert Auto-Scroll bei manueller Navigation.

        Args:
            event: Das Key-Event.
        """
        if event.key in self._NAV_KEYS:
            self._auto_scroll = False

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reagiert auf Aenderungen im Filter-Input."""
        if event.input.id == "filter-bar":
            self.filter_text = event.value
            self._apply_filter()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Reagiert auf Enter/Klick auf eine Zeile."""
        idx = int(event.row_key.value)
        if 0 <= idx < len(self._filtered):
            self.post_message(self.ResultSelected(self._filtered[idx]))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Reagiert auf Cursor-Bewegung."""
        if event.row_key is None:
            return
        idx = int(event.row_key.value)
        if 0 <= idx < len(self._filtered):
            self.post_message(self.ResultHighlighted(self._filtered[idx]))

    def toggle_error_filter(self) -> None:
        """Wechselt zwischen 'alle anzeigen' und 'nur Fehler'."""
        self._show_only_errors = not self._show_only_errors
        self._apply_filter()

    def get_selected_result(self) -> ScanResult | None:
        """Gibt das aktuell ausgewaehlte Ergebnis zurueck.

        Returns:
            Aktuelles ScanResult oder None.
        """
        table = self.query_one("#results-data", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            idx = int(row_key.value)
            if 0 <= idx < len(self._filtered):
                return self._filtered[idx]
        except Exception:
            pass
        return None


def _colored_count(count: int, error_style: str) -> Text:
    """Erstellt einen farbigen Zaehler: rot/gelb bei > 0, dim bei 0.

    Args:
        count: Anzahl der Fehler.
        error_style: Style wenn count > 0.

    Returns:
        Farbcodierter Rich Text.
    """
    if count > 0:
        return Text(str(count), style=error_style)
    return Text("0", style="dim")
