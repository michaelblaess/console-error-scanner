"""DataTable-Widget fuer Scan-Ergebnisse."""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable, Input, Static
from textual_widgets import SearchInputWithHistory


class ResultsDataTable(DataTable):
    """DataTable, die Rechtsklick als ``RightClicked``-Message meldet.

    Ohne diese Subklasse ruft DataTable._on_click bei JEDEM Klick (auch
    Rechtsklick) die Cursor-Move-Logik auf und feuert ggf. ``RowSelected``
    — was die App den Detail-Modal oeffnen laesst, BEVOR mein Container
    den Click ueberhaupt zu Gesicht bekommt.

    Hier wird der Rechtsklick im _on_click (private framework hook,
    laeuft VOR allen Cursor-Aktionen) abgefangen und per ``event.stop()``
    aus der Bubbling-Kette genommen. Andere Buttons → super-Default.
    """

    class RightClicked(Message):
        """Rechtsklick auf einer Datenzeile. ``row_index`` ist der Index."""

        def __init__(self, screen_x: int, screen_y: int, row_index: int) -> None:
            super().__init__()
            self.screen_x = screen_x
            self.screen_y = screen_y
            self.row_index = row_index

    async def _on_click(self, event: events.Click) -> None:
        if event.button == 3:
            meta = event.style.meta if event.style else {}
            row_idx = meta.get("row", -1)
            if isinstance(row_idx, int) and row_idx >= 0:
                event.stop()
                self.post_message(self.RightClicked(event.screen_x, event.screen_y, row_idx))
                return
        await super()._on_click(event)


from ..i18n import t
from ..models.scan_result import PageStatus, ScanResult, format_page_size


class ResultsTable(Vertical):
    """Widget mit filterbarer + sortierbarer DataTable fuer Scan-Ergebnisse."""

    DEFAULT_CSS = """
    ResultsTable {
        height: 1fr;
        layout: vertical;
    }

    /* SearchInputWithHistory rendert eine 3-zeilige Leiste (mit Icon links
       und Input rechts). Keine eigene height-Vorgabe - sonst wird die innere
       search-row auf 1 Zeile gequetscht und ist unsichtbar. */
    ResultsTable SearchInputWithHistory {
        padding: 0 1;
    }

    ResultsTable #results-count {
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

    class ContextRequested(Message):
        """Rechtsklick auf eine Zeile — App soll Kontextmenue oeffnen."""

        def __init__(self, result: ScanResult, screen_x: int, screen_y: int) -> None:
            super().__init__()
            self.result = result
            self.screen_x = screen_x
            self.screen_y = screen_y

    # Spinner-Frames fuer SCANNING-Status
    SPINNER_FRAMES = [">  ", ">> ", ">>>", " >>", "  >", "   "]

    # Tasten bei denen Auto-Scroll deaktiviert wird (manuelle Navigation)
    _NAV_KEYS = {"up", "down", "pageup", "pagedown", "home", "end"}

    # Spaltenindex -> Sortier-Key. Spalten ohne Eintrag sind nicht klickbar.
    _SORT_KEYS: dict[int, Callable[[ScanResult], object]] = {
        1: lambda r: r.status_icon,
        2: lambda r: r.url.lower(),
        3: lambda r: r.http_status_code,
        4: lambda r: r.load_time_ms,
        5: lambda r: r.page_size_bytes,
        6: lambda r: r.console_error_count,
        7: lambda r: r.console_warning_count,
        8: lambda r: r.http_404_count,
        9: lambda r: r.http_4xx_count,
        10: lambda r: r.http_5xx_count,
        11: lambda r: r.ignored_count,
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._results: list[ScanResult] = []
        self._filtered: list[ScanResult] = []
        self._col_keys: list = []
        self._base_column_labels: list[str] = []
        self._show_only_errors: bool = False
        self._spinner_frame: int = 0
        self._spinner_timer = None
        self._auto_scroll: bool = True
        self._auto_scroll_row: int = -1
        self._sort_col: int | None = None
        self._sort_desc: bool = False

    def compose(self) -> ComposeResult:
        """Erstellt die Kind-Widgets."""
        yield SearchInputWithHistory(
            placeholder=t("table.filter_placeholder"),
            icon="🔍",
            input_id="filter-bar",
            dropdown_id="filter-dropdown",
        )
        yield Static("", id="results-count")
        yield ResultsDataTable(id="results-data", cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        """Initialisiert die Tabellenspalten und startet den Spinner-Timer."""
        table = self.query_one("#results-data", DataTable)
        self._base_column_labels = [
            t("table.col_number"),
            t("table.col_status"),
            t("table.col_url"),
            t("table.col_http"),
            t("table.col_time"),
            t("table.col_size"),
            t("table.col_errors"),
            t("table.col_warns"),
            t("table.col_404"),
            t("table.col_4xx"),
            t("table.col_5xx"),
            t("table.col_ignored"),
        ]
        self._col_keys = table.add_columns(*self._base_column_labels)
        self._spinner_timer = self.set_interval(0.3, self._tick_spinner)
        self._update_sort_indicator()

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
                    str(idx),
                    self._col_keys[1],
                    self._styled_status(result),
                )

    def load_results(self, results: list[ScanResult]) -> None:
        """Laedt Ergebnisse in die Tabelle."""
        self._results = results
        self._auto_scroll = True
        self._auto_scroll_row = -1
        self._apply_filter()

    def clear_results(self) -> None:
        """Leert die Ergebnisliste und die DataTable."""
        self._results = []
        self._filtered = []
        self._auto_scroll = True
        self._auto_scroll_row = -1
        with contextlib.suppress(Exception):
            self.query_one("#results-data", DataTable).clear()
        with contextlib.suppress(Exception):
            self.query_one("#results-count", Static).update("")

    def update_result(self, result: ScanResult) -> None:
        """Aktualisiert ein einzelnes Ergebnis in der Tabelle in-place.

        Bei aktivem Filter / aktiver Sortierung wird ein vollstaendiger
        Rebuild durchgefuehrt - die Reihenfolge bzw. Sichtbarkeit kann sich
        durch das neue Ergebnis aendern.
        """
        if self._show_only_errors or self.filter_text or self._sort_col is not None:
            self._rebuild_filtered()
            if self._auto_scroll:
                self._scroll_to_result(result)
            self._refresh_table()
            return

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
        """Aktualisiert alle Zellen einer Zeile in-place."""
        row_key = str(idx)
        status_text = self._styled_status(result)
        scanned = result.status not in (PageStatus.PENDING, PageStatus.SCANNING)

        if scanned:
            errors_text = _colored_count(result.console_error_count, "bold red")
            warns_text = _colored_count(result.console_warning_count, "bold yellow")
            http_404_text = _colored_count(result.http_404_count, "bold yellow")
            http_4xx_text = _colored_count(result.http_4xx_count, "bold yellow")
            http_5xx_text = _colored_count(result.http_5xx_count, "bold red")
            ignored_text = Text(str(result.ignored_count), style="dim")
        else:
            placeholder = Text("-", style="dim")
            errors_text = warns_text = http_404_text = http_4xx_text = http_5xx_text = ignored_text = placeholder

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
        """Merkt sich die Ziel-Zeile fuer Auto-Scroll."""
        try:
            row = self._filtered.index(result)
            if row >= self._auto_scroll_row:
                self._auto_scroll_row = row
        except ValueError:
            pass

    def _rebuild_filtered(self) -> None:
        """Baut die gefilterte und sortierte Liste neu auf."""
        search = self.filter_text.lower()

        filtered: list[ScanResult] = []
        for r in self._results:
            if self._show_only_errors and not r.has_issues:
                continue
            if search and search not in r.url.lower():
                continue
            filtered.append(r)

        if self._sort_col is not None:
            key_func = self._SORT_KEYS.get(self._sort_col)
            if key_func is not None:
                filtered.sort(key=key_func, reverse=self._sort_desc)

        self._filtered = filtered

    def _apply_filter(self) -> None:
        """Wendet den aktuellen Filter an und aktualisiert die Tabelle."""
        self._rebuild_filtered()
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Baut die DataTable komplett neu auf (clear + rebuild)."""
        table = self.query_one("#results-data", DataTable)
        saved_row = table.cursor_row
        table.clear()

        for idx, result in enumerate(self._filtered):
            status_text = self._styled_status(result)
            scanned = result.status not in (PageStatus.PENDING, PageStatus.SCANNING)

            if scanned:
                errors_text = _colored_count(result.console_error_count, "bold red")
                warns_text = _colored_count(result.console_warning_count, "bold yellow")
                http_404_text = _colored_count(result.http_404_count, "bold yellow")
                http_4xx_text = _colored_count(result.http_4xx_count, "bold yellow")
                http_5xx_text = _colored_count(result.http_5xx_count, "bold red")
                ignored_text = Text(str(result.ignored_count), style="dim")
            else:
                placeholder = Text("-", style="dim")
                errors_text = warns_text = http_404_text = http_4xx_text = http_5xx_text = ignored_text = placeholder

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
            count_label.update(t("table.count", count=total))
        else:
            count_label.update(t("table.count_filtered", shown=shown, total=total))

    def _styled_status(self, result: ScanResult) -> Text:
        """Erstellt farbcodierten Status-Text."""
        if result.status == PageStatus.SCANNING:
            frame = self.SPINNER_FRAMES[self._spinner_frame % len(self.SPINNER_FRAMES)]
            return Text(frame, style="bold cyan")

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

    # --- Sortierung ------------------------------------------------------

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Header-Klick: gleiche Spalte = Richtung toggeln, andere = neue Spalte."""
        try:
            col_index = self._col_keys.index(event.column_key)
        except ValueError:
            return
        if col_index not in self._SORT_KEYS:
            return
        if col_index == self._sort_col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col_index
            self._sort_desc = False
        self._update_sort_indicator()
        self._apply_filter()

    def _update_sort_indicator(self) -> None:
        """Setzt ▲/▼ am aktiv sortierten Spaltenkopf, alle anderen ohne Pfeil."""
        if not self._col_keys or not self._base_column_labels:
            return
        try:
            table = self.query_one("#results-data", DataTable)
        except Exception:
            return
        arrow = " ▼" if self._sort_desc else " ▲"
        for idx, key in enumerate(self._col_keys):
            base = self._base_column_labels[idx]
            label = f"{base}{arrow}" if idx == self._sort_col else base
            col = table.columns.get(key)
            if col is not None:
                col.label = Text(label)
        table.refresh()

    # --- Filter ----------------------------------------------------------

    def on_key(self, event) -> None:
        """Deaktiviert Auto-Scroll bei manueller Navigation."""
        if event.key in self._NAV_KEYS:
            self._auto_scroll = False

    def on_results_data_table_right_clicked(self, event: ResultsDataTable.RightClicked) -> None:
        """Rechtsklick aus der DataTable-Subklasse → ContextRequested melden."""
        if not (0 <= event.row_index < len(self._filtered)):
            return
        result = self._filtered[event.row_index]
        # Cursor auf die geklickte Zeile setzen (visuelles Feedback)
        with contextlib.suppress(Exception):
            self.query_one("#results-data", DataTable).move_cursor(row=event.row_index)
        self.post_message(self.ContextRequested(result, event.screen_x, event.screen_y))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reagiert auf Aenderungen im Filter-Input."""
        if event.input.id == "filter-bar":
            self.filter_text = event.value
            self._apply_filter()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Reagiert auf Enter/Klick auf eine Zeile (nur Links-Klick)."""
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

    def toggle_error_filter(self) -> bool:
        """Wechselt zwischen 'alle anzeigen' und 'nur Fehler'.

        Returns:
            True wenn der Error-Filter jetzt aktiv ist.
        """
        self._show_only_errors = not self._show_only_errors
        self._apply_filter()
        return self._show_only_errors

    def get_selected_result(self) -> ScanResult | None:
        """Gibt das aktuell ausgewaehlte Ergebnis zurueck."""
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
    """Erstellt einen farbigen Zaehler: rot/gelb bei > 0, dim bei 0."""
    if count > 0:
        return Text(str(count), style=error_style)
    return Text("0", style="dim")
