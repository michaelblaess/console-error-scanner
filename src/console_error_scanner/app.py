"""Hauptanwendung fuer Console Error Scanner."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, RichLog

from . import __version__, __year__
from .models.scan_result import ScanResult, ScanSummary, PageStatus
from .models.sitemap import SitemapParser, SitemapError
from .services.reporter import Reporter
from .services.scanner import Scanner
from .widgets.error_detail_view import ErrorDetailView
from .widgets.results_table import ResultsTable
from .widgets.summary_panel import SummaryPanel


# Log-Hoehe: min/max/default (Zeilen)
LOG_HEIGHT_DEFAULT = 15
LOG_HEIGHT_MIN = 5
LOG_HEIGHT_MAX = 35
LOG_HEIGHT_STEP = 3


class ConsoleErrorScannerApp(App):
    """TUI-Anwendung zum Scannen von Websites auf Console- und HTTP-Fehler."""

    CSS_PATH = "app.tcss"
    TITLE = f"Console Error Scanner v{__version__} ({__year__})"

    BINDINGS = [
        Binding("q", "quit", "Beenden"),
        Binding("s", "start_scan", "Scan"),
        Binding("r", "save_reports", "Report"),
        Binding("t", "show_top_errors", "Top 10"),
        Binding("l", "toggle_log", "Log"),
        Binding("e", "toggle_errors", "Nur Fehler"),
        Binding("plus", "log_bigger", "Log +", key_display="+"),
        Binding("minus", "log_smaller", "Log -", key_display="-"),
        Binding("slash", "focus_filter", "Filter", key_display="/"),
        Binding("escape", "unfocus_filter", "Filter leeren", show=False),
        Binding("c", "copy_log", "Log kopieren"),
        Binding("i", "show_about", "Info"),
    ]

    def __init__(
        self,
        sitemap_url: str = "",
        concurrency: int = 8,
        timeout: int = 30,
        output_json: str = "",
        output_html: str = "",
        headless: bool = True,
        url_filter: str = "",
        console_level: str = "warn",
        user_agent: str = "",
        cookies: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self.sitemap_url = sitemap_url
        self.concurrency = concurrency
        self.timeout = timeout
        self.output_json = output_json
        self.output_html = output_html
        self.headless = headless
        self.url_filter = url_filter
        self.console_level = console_level
        self.user_agent = user_agent
        self.cookies = cookies or []
        self._urls: list[str] = []
        self._results: list[ScanResult] = []
        self._scanner: Scanner | None = None
        self._scan_running: bool = False
        self._scan_start_time: float = 0
        self._log_lines: list[str] = []
        self._log_height: int = LOG_HEIGHT_DEFAULT

    def compose(self) -> ComposeResult:
        """Erstellt das UI-Layout."""
        yield Header()
        yield SummaryPanel(id="summary")

        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield ResultsTable(id="results-table")
                yield RichLog(id="scan-log", highlight=True, markup=True)

            yield ErrorDetailView(id="error-detail")

        yield Footer()

    def on_mount(self) -> None:
        """Initialisierung nach dem Starten."""
        # Versionsinfo ins Log schreiben
        self._write_log(f"[bold]Console Error Scanner v{__version__}[/bold]")
        self._write_log(f"Concurrency: {self.concurrency} | Timeout: {self.timeout}s | Console-Level: {self.console_level}")

        # Focus auf die Tabelle setzen damit Footer-Bindings sofort sichtbar
        try:
            from textual.widgets import DataTable
            table = self.query_one("#results-data", DataTable)
            table.focus()
        except Exception:
            pass

        if self.sitemap_url:
            self._load_sitemap()

    @work(exclusive=True)
    async def _load_sitemap(self) -> None:
        """Laedt die Sitemap und zeigt die URLs an."""
        self._write_log(f"Lade Sitemap: {self.sitemap_url}")

        try:
            parser = SitemapParser(self.sitemap_url, url_filter=self.url_filter, cookies=self.cookies)
            self._urls = await parser.parse()
        except SitemapError as e:
            self._write_log(f"[red]Sitemap-Fehler: {e}[/red]")
            self.app.push_screen(
                _SitemapErrorScreen(f"Sitemap-Fehler:\n\n{e}")
            )
            return
        except Exception as e:
            self._write_log(f"[red]Unerwarteter Fehler: {e}[/red]")
            self.app.push_screen(
                _SitemapErrorScreen(f"Unerwarteter Fehler:\n\n{e}")
            )
            return

        if not self._urls:
            self._write_log("[yellow]Keine URLs in der Sitemap gefunden.[/yellow]")
            self.notify("Keine URLs gefunden!", severity="warning")
            return

        self._write_log(f"[green]{len(self._urls)} URLs geladen[/green]")

        # Ergebnisse initialisieren
        self._results = [ScanResult(url=url) for url in self._urls]

        # UI aktualisieren
        summary = self.query_one("#summary", SummaryPanel)
        summary.set_sitemap(self.sitemap_url, len(self._urls))

        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        self.sub_title = f"{len(self._urls)} URLs"

        # Auto-Scan starten wenn CLI-Reports angefordert
        if self.output_json or self.output_html:
            self.action_start_scan()

    @work(exclusive=True)
    async def action_start_scan(self) -> None:
        """Startet den Scan aller URLs."""
        if self._scan_running:
            self.notify("Scan laeuft bereits!", severity="warning")
            return

        if not self._urls:
            self.notify("Keine URLs geladen! Bitte zuerst eine Sitemap laden.", severity="error")
            return

        self._scan_running = True
        self._scan_start_time = time.monotonic()

        # Log einblenden
        log_widget = self.query_one("#scan-log", RichLog)
        log_widget.remove_class("hidden")
        log_widget.clear()
        self._log_lines.clear()

        # Ergebnisse zuruecksetzen (gleiche Objekte behalten!)
        for result in self._results:
            result.status = PageStatus.PENDING
            result.http_status_code = 0
            result.load_time_ms = 0
            result.errors.clear()
            result.retry_count = 0

        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        self._scanner = Scanner(
            concurrency=self.concurrency,
            timeout=self.timeout,
            headless=self.headless,
            console_level=self.console_level,
            user_agent=self.user_agent,
            cookies=self.cookies,
        )

        # Async Worker laeuft im Textual-Event-Loop,
        # daher direkt auf Widgets zugreifen (kein call_from_thread!)
        def on_result(result: ScanResult) -> None:
            """Callback fuer jedes einzelne Ergebnis."""
            self._on_scan_result(result)

        def on_log(msg: str) -> None:
            """Callback fuer Log-Nachrichten."""
            self._write_log(msg)

        def on_progress(current: int, total: int) -> None:
            """Callback fuer Fortschritt."""
            self._on_scan_progress(current, total)

        try:
            # Scanner bekommt die GLEICHEN ScanResult-Objekte
            await self._scanner.scan_urls(
                self._results,
                on_result=on_result,
                on_log=on_log,
                on_progress=on_progress,
            )
        except Exception as e:
            self._write_log(f"[red]Scan-Fehler: {e}[/red]")
            self.notify(f"Scan-Fehler: {e}", severity="error")
        finally:
            self._scan_running = False
            self._scanner = None

        # Scan abgeschlossen
        duration_ms = int((time.monotonic() - self._scan_start_time) * 1000)
        summary_data = ScanSummary.from_results(self.sitemap_url, self._results, duration_ms)

        self._write_log(f"\n[bold green]Scan abgeschlossen in {duration_ms / 1000:.1f}s[/bold green]")
        self._write_log(
            f"Ergebnis: {summary_data.urls_with_errors} Seiten mit Fehlern | "
            f"Console: {summary_data.total_console_errors} | "
            f"404: {summary_data.total_http_404} | "
            f"4xx: {summary_data.total_http_4xx} | "
            f"5xx: {summary_data.total_http_5xx}"
        )

        # Tabelle final aktualisieren
        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        # Summary aktualisieren
        summary = self.query_one("#summary", SummaryPanel)
        summary.update_from_results(self._results)

        self.sub_title = f"{len(self._urls)} URLs - Scan abgeschlossen"

        # Auto-Reports speichern (CLI-Parameter)
        if self.output_json or self.output_html:
            self._save_reports_auto(summary_data)

    def _on_scan_result(self, result: ScanResult) -> None:
        """Verarbeitet ein einzelnes Scan-Ergebnis (Live-Update).

        Args:
            result: Das aktualisierte ScanResult (gleiches Objekt wie in self._results).
        """
        table = self.query_one("#results-table", ResultsTable)
        table.update_result(result)

        summary = self.query_one("#summary", SummaryPanel)
        summary.update_from_results(self._results)

        # Detail-View aktualisieren falls diese URL gerade angezeigt wird
        detail = self.query_one("#error-detail", ErrorDetailView)
        if detail._result is result:
            detail.refresh()

    def _on_scan_progress(self, current: int, total: int) -> None:
        """Aktualisiert den Fortschritt.

        Args:
            current: Aktuell abgeschlossene URLs.
            total: Gesamtanzahl URLs.
        """
        self.sub_title = f"Scanning... {current}/{total}"

    def on_results_table_result_highlighted(
        self, event: ResultsTable.ResultHighlighted
    ) -> None:
        """Aktualisiert die Detail-Ansicht beim Cursor-Wechsel."""
        detail = self.query_one("#error-detail", ErrorDetailView)
        detail.show_result(event.result)

    def on_results_table_result_selected(
        self, event: ResultsTable.ResultSelected
    ) -> None:
        """Oeffnet den Detail-Dialog bei Enter/Doppelklick."""
        from .screens.error_detail import ErrorDetailScreen
        self.push_screen(ErrorDetailScreen(event.result))

    def action_save_reports(self) -> None:
        """Speichert HTML- und JSON-Reports."""
        if not self._results:
            self.notify("Keine Ergebnisse vorhanden!", severity="warning")
            return

        # Nur gescannte Ergebnisse pruefen
        scanned = [r for r in self._results if r.status not in (PageStatus.PENDING, PageStatus.SCANNING)]
        if not scanned:
            self.notify("Noch keine Seiten gescannt!", severity="warning")
            return

        duration_ms = int((time.monotonic() - self._scan_start_time) * 1000) if self._scan_start_time > 0 else 0
        summary = ScanSummary.from_results(self.sitemap_url, self._results, duration_ms)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON
        json_path = f"console-error-report_{timestamp}.json"
        saved_json = Reporter.save_json(self._results, summary, json_path)
        self._write_log(f"[green]JSON-Report: {saved_json}[/green]")

        # HTML
        html_path = f"console-error-report_{timestamp}.html"
        saved_html = Reporter.save_html(self._results, summary, html_path)
        self._write_log(f"[green]HTML-Report: {saved_html}[/green]")

        self.notify(f"Reports gespeichert: {json_path}, {html_path}")

    def _save_reports_auto(self, summary: ScanSummary) -> None:
        """Speichert Reports automatisch (CLI-Parameter).

        Args:
            summary: Scan-Zusammenfassung.
        """
        if self.output_json:
            path = Reporter.save_json(self._results, summary, self.output_json)
            self._write_log(f"[green]JSON-Report: {path}[/green]")

        if self.output_html:
            path = Reporter.save_html(self._results, summary, self.output_html)
            self._write_log(f"[green]HTML-Report: {path}[/green]")

    def action_copy_log(self) -> None:
        """Kopiert das Log in die Zwischenablage."""
        if not self._log_lines:
            self.notify("Log ist leer.", severity="warning")
            return

        text = "\n".join(self._log_lines)
        self.copy_to_clipboard(text)
        self.notify(f"Log kopiert ({len(self._log_lines)} Zeilen)")

    def action_show_top_errors(self) -> None:
        """Zeigt den Top-10-Fehler Dialog."""
        if not self._results:
            self.notify("Keine Ergebnisse vorhanden!", severity="warning")
            return

        from .screens.top_errors import TopErrorsScreen
        self.push_screen(TopErrorsScreen(self._results))

    def action_toggle_log(self) -> None:
        """Blendet den Log-Bereich ein/aus."""
        log_widget = self.query_one("#scan-log", RichLog)
        log_widget.toggle_class("hidden")

    def action_log_bigger(self) -> None:
        """Vergroessert den Log-Bereich."""
        self._log_height = min(self._log_height + LOG_HEIGHT_STEP, LOG_HEIGHT_MAX)
        log_widget = self.query_one("#scan-log", RichLog)
        log_widget.styles.height = self._log_height

    def action_log_smaller(self) -> None:
        """Verkleinert den Log-Bereich."""
        self._log_height = max(self._log_height - LOG_HEIGHT_STEP, LOG_HEIGHT_MIN)
        log_widget = self.query_one("#scan-log", RichLog)
        log_widget.styles.height = self._log_height

    def action_toggle_errors(self) -> None:
        """Wechselt zwischen alle/nur Fehler in der Tabelle."""
        table = self.query_one("#results-table", ResultsTable)
        table.toggle_error_filter()

    def action_focus_filter(self) -> None:
        """Fokussiert das Filter-Eingabefeld."""
        try:
            from textual.widgets import Input
            filter_input = self.query_one("#filter-bar", Input)
            filter_input.focus()
        except Exception:
            pass

    def action_unfocus_filter(self) -> None:
        """Leert den Filter und gibt Focus zurueck an die Tabelle."""
        try:
            from textual.widgets import Input, DataTable
            filter_input = self.query_one("#filter-bar", Input)
            filter_input.value = ""
            table = self.query_one("#results-data", DataTable)
            table.focus()
        except Exception:
            pass

    def action_show_about(self) -> None:
        """Zeigt den About-Dialog an."""
        from .screens.about import AboutScreen
        self.push_screen(AboutScreen())

    def _write_log(self, line: str) -> None:
        """Schreibt eine Zeile ins Log-Widget und in den Puffer.

        Args:
            line: Log-Nachricht (kann Rich-Markup enthalten).
        """
        self._log_lines.append(line)
        try:
            self.query_one("#scan-log", RichLog).write(line)
        except Exception:
            pass


class _SitemapErrorScreen(ModalScreen):
    """Modal-Dialog fuer Sitemap-Fehler."""

    DEFAULT_CSS = """
    _SitemapErrorScreen {
        align: center middle;
    }

    _SitemapErrorScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 20;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    _SitemapErrorScreen #error-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $error;
        color: $text;
        margin-bottom: 1;
    }

    _SitemapErrorScreen #error-message {
        height: auto;
        padding: 1;
    }

    _SitemapErrorScreen #error-footer {
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

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._message = message

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        from textual.containers import Vertical
        from textual.widgets import Static

        with Vertical():
            yield Static("Fehler", id="error-title")
            yield Static(self._message, id="error-message")
            yield Static("ESC = Schliessen", id="error-footer")

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss()
