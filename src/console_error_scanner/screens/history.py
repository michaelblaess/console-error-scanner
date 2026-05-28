"""History-Screen fuer Console Error Scanner.

Zeigt eine Liste vergangener Scans und ermoeglicht die Wiederholung
eines ausgewaehlten Scans.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ..i18n import t
from ..models.history import History, HistoryEntry


class HistoryScreen(ModalScreen[HistoryEntry | None]):
    """Modal-Dialog zur Anzeige und Auswahl vergangener Scans.

    Gibt den ausgewaehlten HistoryEntry per dismiss() zurueck
    oder None wenn der Dialog ohne Auswahl geschlossen wird.
    """

    DEFAULT_CSS = """
    HistoryScreen {
        align: center middle;
    }

    HistoryScreen > Vertical {
        width: 110;
        height: 35;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    HistoryScreen #history-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: $text;
        margin-bottom: 1;
    }

    HistoryScreen #history-empty {
        height: auto;
        padding: 2 4;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }

    HistoryScreen #history-table {
        height: 1fr;
    }

    HistoryScreen #history-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    HistoryScreen #history-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries: list[HistoryEntry] = []

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        self._entries = History.load()

        with Vertical():
            yield Static(t("history.title"), id="history-title")

            if not self._entries:
                yield Static(
                    t("history.empty"),
                    id="history-empty",
                )
            else:
                table = DataTable(id="history-table", cursor_type="row")
                table.add_columns(
                    t("history.col_number"),
                    t("history.col_date"),
                    t("history.col_url"),
                    t("history.col_params"),
                )
                for idx, entry in enumerate(self._entries, start=1):
                    # Datum kuerzen
                    date_str = entry.timestamp[:16].replace("T", " ") if entry.timestamp else "?"

                    # Hostname extrahieren
                    from urllib.parse import urlparse

                    try:
                        host = urlparse(entry.sitemap_url).hostname or entry.sitemap_url
                    except Exception:
                        host = entry.sitemap_url

                    # Parameter kompakt zusammenbauen
                    params = []
                    if entry.cookies:
                        cookie_names = ", ".join(c.get("name", "?") for c in entry.cookies)
                        params.append(f"--cookie {cookie_names}")
                    if entry.whitelist_path:
                        params.append(f"--whitelist {entry.whitelist_path}")
                    if entry.url_filter:
                        params.append(f"--filter {entry.url_filter}")
                    if entry.console_level != "warn":
                        params.append(f"--level {entry.console_level}")
                    if entry.concurrency != 8:
                        params.append(f"-c {entry.concurrency}")
                    if entry.timeout != 60:
                        params.append(f"-t {entry.timeout}")
                    if entry.user_agent:
                        params.append("--user-agent ...")
                    if not entry.accept_consent:
                        params.append("--no-consent")
                    param_str = "  ".join(params) if params else "-"

                    table.add_row(str(idx), date_str, host, param_str, key=str(idx))

                yield table

            with Horizontal(id="history-buttons"):
                yield Button(t("history.btn_select"), variant="primary", id="history-select")
                yield Button(t("history.btn_close"), variant="default", id="history-close")

    def on_mount(self) -> None:
        """Fokussiert die Tabelle nach dem Oeffnen."""
        if self._entries:
            try:
                table = self.query_one("#history-table", DataTable)
                table.focus()
            except Exception:
                pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Verarbeitet die Auswahl einer Zeile (Enter/Doppelklick).

        Args:
            event: Das RowSelected-Event mit dem Key der Zeile.
        """
        try:
            idx = int(str(event.row_key.value)) - 1
            if 0 <= idx < len(self._entries):
                self.dismiss(self._entries[idx])
        except (ValueError, IndexError):
            pass

    @on(Button.Pressed, "#history-select")
    def _on_select_button(self) -> None:
        """Übernimmt die markierte Zeile."""
        if not self._entries:
            self.dismiss(None)
            return
        try:
            table = self.query_one("#history-table", DataTable)
            row = table.cursor_row
            if 0 <= row < len(self._entries):
                self.dismiss(self._entries[row])
                return
        except Exception:
            pass
        self.dismiss(None)

    @on(Button.Pressed, "#history-close")
    def _on_close_button(self) -> None:
        """Schließt den Dialog ohne Auswahl."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Schließt den Dialog ohne Auswahl (ESC/q)."""
        self.dismiss(None)
