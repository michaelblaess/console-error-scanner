"""Hauptanwendung fuer Console Error Scanner."""

from __future__ import annotations

import asyncio
import dataclasses
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Footer, Header, RichLog

from textual_themes import register_all

from . import __version__, __year__
from .i18n import t
from .models.history import History, HistoryEntry
from .models.settings import Settings
from .models.scan_result import ScanResult, ScanSummary, PageStatus
from .models.sitemap import SitemapParser, SitemapError, discover_sitemap, is_sitemap_url, is_local_file
from .models.whitelist import Whitelist
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

    def __init__(
        self,
        sitemap_url: str = "",
        concurrency: int = 8,
        timeout: int = 60,
        output_json: str = "",
        output_html: str = "",
        headless: bool = True,
        url_filter: str = "",
        console_level: str = "warn",
        user_agent: str = "",
        cookies: list[dict[str, str]] | None = None,
        whitelist_path: str = "",
        accept_consent: bool | None = None,
        trigger_lazy_load: bool | None = None,
    ) -> None:
        super().__init__()

        # Bindings mit uebersetzten Labels
        self._bindings.bind("q", "quit", t("binding.quit"))
        self._bindings.bind("s", "start_scan", t("binding.scan"))
        self._bindings.bind("h", "show_history", t("binding.history"))
        self._bindings.bind("r", "save_reports", t("binding.report"))
        self._bindings.bind("t", "show_top_errors", t("binding.top_errors"))
        self._bindings.bind("w", "toggle_whitelist", t("binding.whitelist_on"))
        self._bindings.bind("l", "toggle_log", t("binding.log"))
        self._bindings.bind("e", "toggle_errors", t("binding.errors_only"))
        self._bindings.bind("plus", "log_bigger", t("binding.log_bigger"), key_display="+")
        self._bindings.bind("minus", "log_smaller", t("binding.log_smaller"), key_display="-")
        self._bindings.bind("slash", "focus_filter", t("binding.filter"), key_display="/")
        self._bindings.bind("escape", "unfocus_filter", t("binding.clear_filter"), show=False)
        self._bindings.bind("n", "toggle_consent", t("binding.consent_on"))
        self._bindings.bind("g", "toggle_scroll", t("binding.scroll_on"))
        self._bindings.bind("c", "copy_log", t("binding.copy_log"))
        self._bindings.bind("d", "copy_details", t("binding.copy_details"))
        self._bindings.bind("i", "show_about", t("binding.info"))

        # Retro-Themes registrieren (C64, Amiga, Atari ST, IBM Terminal, NeXTSTEP, BeOS)
        register_all(self)

        # Persistierte Einstellungen laden
        self._settings = Settings.load()

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
        self.whitelist_path = whitelist_path

        # Consent: CLI-Parameter hat Vorrang, sonst aus Settings
        self.accept_consent = accept_consent if accept_consent is not None else self._settings.accept_consent

        # Scroll/Lazy-Load: CLI-Parameter hat Vorrang, sonst aus Settings
        self.trigger_lazy_load = trigger_lazy_load if trigger_lazy_load is not None else self._settings.trigger_lazy_load

        # Theme aus Settings uebernehmen
        self.theme = self._settings.theme

        self._urls: list[str] = []
        self._results: list[ScanResult] = []
        self._scanner: Scanner | None = None
        self._whitelist: Whitelist | None = None
        self._whitelist_active: bool = False
        self._sitemap_loading: bool = False
        self._sitemap_timer: Timer | None = None
        self._sitemap_dots: int = 0
        self._scan_running: bool = False
        self._scan_start_time: float = 0
        self._scan_current: int = 0
        self._scan_total: int = 0
        self._scan_progress_timer: Timer | None = None
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
        self._write_log(f"[bold]{t('log.version', version=__version__)}[/bold]")
        consent_info = t("log.consent_on") if self.accept_consent else t("log.consent_off")
        scroll_info = t("log.scroll_on") if self.trigger_lazy_load else t("log.scroll_off")
        self._write_log(t("log.config", concurrency=self.concurrency, timeout=self.timeout, level=self.console_level, consent=consent_info, scroll=scroll_info))

        # Consent-Binding-Label aktualisieren falls --no-consent
        if not self.accept_consent:
            bindings_list = self._bindings.key_to_bindings.get("n", [])
            for i, binding in enumerate(bindings_list):
                if binding.action == "toggle_consent":
                    self._bindings.key_to_bindings["n"][i] = dataclasses.replace(
                        binding, description=t("binding.consent_off")
                    )
                    break
            self.refresh_bindings()

        # Scroll-Binding-Label aktualisieren falls --no-scroll
        if not self.trigger_lazy_load:
            bindings_list = self._bindings.key_to_bindings.get("g", [])
            for i, binding in enumerate(bindings_list):
                if binding.action == "toggle_scroll":
                    self._bindings.key_to_bindings["g"][i] = dataclasses.replace(
                        binding, description=t("binding.scroll_off")
                    )
                    break
            self.refresh_bindings()

        # Whitelist laden (wenn angegeben oder whitelist.json im CWD vorhanden)
        if not self.whitelist_path:
            cwd_whitelist = Path("whitelist.json")
            if cwd_whitelist.is_file():
                self.whitelist_path = str(cwd_whitelist)

        if self.whitelist_path:
            try:
                self._whitelist = Whitelist.load(self.whitelist_path)
                self._whitelist_active = True
                self._write_log(f"[green]{t('log.whitelist_loaded', count=len(self._whitelist), path=self.whitelist_path)}[/green]")
                for pattern in self._whitelist.patterns:
                    self._write_log(f"[dim]  - {pattern}[/dim]")
            except Exception as e:
                self._write_log(f"[red]{t('log.whitelist_error', error=e)}[/red]")
                self._whitelist = None
                self._whitelist_active = False

        # Focus auf die Tabelle setzen damit Footer-Bindings sofort sichtbar
        try:
            from textual.widgets import DataTable
            table = self.query_one("#results-data", DataTable)
            table.focus()
        except Exception:
            pass

        if self.sitemap_url:
            self._load_sitemap()

    def _start_sitemap_loading(self) -> None:
        """Startet die Lade-Animation fuer die Sitemap."""
        self._sitemap_loading = True
        self._sitemap_dots = 0
        self.sub_title = t("subtitle.loading_sitemap")
        self.refresh_bindings()
        self._sitemap_timer = self.set_interval(0.5, self._tick_sitemap_loading)

    def _tick_sitemap_loading(self) -> None:
        """Timer-Callback: Schreibt Fortschrittspunkte ins Log."""
        self._sitemap_dots += 1
        dots = "." * self._sitemap_dots
        self.sub_title = t("subtitle.loading_sitemap_dots", dots=dots)

    def _stop_sitemap_loading(self) -> None:
        """Stoppt die Lade-Animation."""
        if self._sitemap_timer is not None:
            self._sitemap_timer.stop()
            self._sitemap_timer = None
        self._sitemap_loading = False
        self._sitemap_dots = 0
        self.refresh_bindings()

    @work(exclusive=True, group="sitemap")
    async def _load_sitemap(self) -> None:
        """Laedt die Sitemap und zeigt die URLs an.

        Wenn die URL nicht auf .xml endet, wird automatisch versucht
        die Sitemap via robots.txt und typische Pfade zu finden.
        """
        self._start_sitemap_loading()

        # Lokale Datei: direkt laden, keine Discovery
        if is_local_file(self.sitemap_url):
            self._write_log(t("log.loading_local_sitemap", url=self.sitemap_url))
        elif not is_sitemap_url(self.sitemap_url):
            # Auto-Discovery wenn keine direkte Sitemap-URL
            self._write_log(t("log.searching_sitemap", url=self.sitemap_url))
            try:
                self.sitemap_url = await discover_sitemap(
                    self.sitemap_url,
                    cookies=self.cookies,
                    log=self._write_log,
                )
            except SitemapError as e:
                self._stop_sitemap_loading()
                self._write_log(f"[red]{t('log.sitemap_error', error=e)}[/red]")
                self.app.push_screen(
                    _SitemapErrorScreen(t("sitemap_error.sitemap_error", error=e))
                )
                return
            self._write_log(t("log.loading_sitemap_url", url=self.sitemap_url))
        else:
            self._write_log(t("log.loading_sitemap_url", url=self.sitemap_url))

        try:
            parser = SitemapParser(self.sitemap_url, url_filter=self.url_filter, cookies=self.cookies)
            self._urls = await parser.parse()
        except SitemapError as e:
            self._stop_sitemap_loading()
            self._write_log(f"[red]{t('log.sitemap_error', error=e)}[/red]")
            self.app.push_screen(
                _SitemapErrorScreen(t("sitemap_error.sitemap_error", error=e))
            )
            return
        except Exception as e:
            self._stop_sitemap_loading()
            self._write_log(f"[red]{t('log.unexpected_error', error=e)}[/red]")
            self.app.push_screen(
                _SitemapErrorScreen(t("sitemap_error.unexpected_error", error=e))
            )
            return

        self._stop_sitemap_loading()

        if not self._urls:
            self._write_log(f"[yellow]{t('log.no_urls_in_sitemap')}[/yellow]")
            self.notify(t("notify.no_urls"), severity="warning")
            return

        self._write_log(f"[green]{t('log.urls_loaded', count=len(self._urls))}[/green]")

        # Ergebnisse initialisieren
        self._results = [ScanResult(url=url) for url in self._urls]

        # UI aktualisieren
        summary = self.query_one("#summary", SummaryPanel)
        summary.set_sitemap(self.sitemap_url, len(self._urls))

        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        self.sub_title = t("subtitle.urls_count", count=len(self._urls))

        # Auto-Scan starten wenn CLI-Reports angefordert
        if self.output_json or self.output_html:
            self.action_start_scan()

    @work(exclusive=True, group="scan")
    async def action_start_scan(self) -> None:
        """Startet den Scan aller URLs."""
        if self._scan_running:
            self.notify(t("notify.scan_running"), severity="warning")
            return

        if not self._urls:
            self.notify(t("notify.no_urls_loaded"), severity="error")
            return

        self._scan_running = True
        self._scan_start_time = time.monotonic()
        self._scan_current = 0
        self._scan_total = len(self._results)
        self._scan_progress_timer = self.set_interval(0.5, self._tick_scan_progress)

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
            result.page_size_bytes = 0
            result.errors.clear()
            result.retry_count = 0

        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        # History-Eintrag erstellen und speichern
        try:
            history_entry = HistoryEntry(
                sitemap_url=self.sitemap_url,
                concurrency=self.concurrency,
                timeout=self.timeout,
                console_level=self.console_level,
                url_filter=self.url_filter,
                user_agent=self.user_agent,
                cookies=list(self.cookies),
                whitelist_path=self.whitelist_path,
                accept_consent=self.accept_consent,
                trigger_lazy_load=self.trigger_lazy_load,
            )
            History.add(history_entry)
            self._write_log(f"[dim]{t('log.history_updated')}[/dim]")
        except Exception:
            pass

        self._scanner = Scanner(
            concurrency=self.concurrency,
            timeout=self.timeout,
            headless=self.headless,
            console_level=self.console_level,
            user_agent=self.user_agent,
            cookies=self.cookies,
            accept_consent=self.accept_consent,
            trigger_lazy_load=self.trigger_lazy_load,
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
            self._write_log(f"[red]{t('log.sitemap_error', error=e)}[/red]")
            self.notify(t("notify.scan_error", error=e), severity="error")
        finally:
            self._scan_running = False
            self._scanner = None
            if self._scan_progress_timer is not None:
                self._scan_progress_timer.stop()
                self._scan_progress_timer = None

        # Scan abgeschlossen
        duration_ms = int((time.monotonic() - self._scan_start_time) * 1000)
        summary_data = ScanSummary.from_results(self.sitemap_url, self._results, duration_ms)

        self._write_log(f"\n[bold green]{t('log.scan_complete', duration=_format_duration(duration_ms))}[/bold green]")
        ignored_info = f" | Ignored: {summary_data.total_ignored}" if summary_data.total_ignored > 0 else ""
        self._write_log(t(
            "log.scan_result",
            errors_pages=summary_data.urls_with_errors,
            console=summary_data.total_console_errors,
            http_404=summary_data.total_http_404,
            http_4xx=summary_data.total_http_4xx,
            http_5xx=summary_data.total_http_5xx,
            ignored=ignored_info,
        ))
        if summary_data.total_ignored > 0:
            self._write_log(f"[dim]{t('log.whitelist_suppressed', count=summary_data.total_ignored)}[/dim]")

        # Tabelle final aktualisieren
        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        # Summary aktualisieren
        summary = self.query_one("#summary", SummaryPanel)
        summary.update_from_results(self._results)

        self.sub_title = t("subtitle.scan_complete", count=len(self._urls))

        # Auto-Reports speichern (CLI-Parameter)
        if self.output_json or self.output_html:
            self._save_reports_auto(summary_data)

    def _on_scan_result(self, result: ScanResult) -> None:
        """Verarbeitet ein einzelnes Scan-Ergebnis (Live-Update).

        Args:
            result: Das aktualisierte ScanResult (gleiches Objekt wie in self._results).
        """
        # Whitelist anwenden bevor UI aktualisiert wird
        if self._whitelist and self._whitelist_active:
            self._whitelist.apply(result)

        table = self.query_one("#results-table", ResultsTable)
        table.update_result(result)

        summary = self.query_one("#summary", SummaryPanel)
        summary.update_from_results(self._results)

        # Detail-View aktualisieren falls diese URL gerade angezeigt wird
        detail = self.query_one("#error-detail", ErrorDetailView)
        if detail._result is result:
            detail.refresh()

    def _on_scan_progress(self, current: int, total: int) -> None:
        """Speichert den Fortschritt (Timer aktualisiert die Anzeige).

        Args:
            current: Aktuell abgeschlossene URLs.
            total: Gesamtanzahl URLs.
        """
        self._scan_current = current
        self._scan_total = total

    def _tick_scan_progress(self) -> None:
        """Timer-Callback: Aktualisiert den Fortschrittsbalken im Header."""
        current = self._scan_current
        total = self._scan_total
        bar = _format_progress_bar(current, total)
        pct = int(current / total * 100) if total > 0 else 0

        elapsed = time.monotonic() - self._scan_start_time
        if current > 0:
            avg_per_url = elapsed / current
            remaining_s = avg_per_url * (total - current)
            remaining = _format_duration(int(remaining_s * 1000))
            self.sub_title = t(
                "subtitle.scanning",
                bar=bar, pct=pct, current=current, total=total,
                remaining=remaining, avg=f"{avg_per_url:.1f}",
            )
        else:
            self.sub_title = t("subtitle.scanning_start", bar=bar, total=total)

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
            self.notify(t("notify.no_results"), severity="warning")
            return

        # Nur gescannte Ergebnisse pruefen
        scanned = [r for r in self._results if r.status not in (PageStatus.PENDING, PageStatus.SCANNING)]
        if not scanned:
            self.notify(t("notify.not_scanned"), severity="warning")
            return

        duration_ms = int((time.monotonic() - self._scan_start_time) * 1000) if self._scan_start_time > 0 else 0
        summary = ScanSummary.from_results(self.sitemap_url, self._results, duration_ms)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        site_name = _sanitize_filename(urlparse(self.sitemap_url).hostname or "unknown")
        base_name = f"console-error-report_{site_name}_{timestamp}"

        # JSON
        json_path = f"{base_name}.json"
        saved_json = Reporter.save_json(self._results, summary, json_path)
        self._write_log(f"[green]{t('log.json_report', path=saved_json)}[/green]")

        # HTML
        html_path = f"{base_name}.html"
        saved_html = Reporter.save_html(self._results, summary, html_path)
        self._write_log(f"[green]{t('log.html_report', path=saved_html)}[/green]")

        self.notify(t("notify.reports_saved", json_path=json_path, html_path=html_path))

    def _save_reports_auto(self, summary: ScanSummary) -> None:
        """Speichert Reports automatisch (CLI-Parameter).

        Args:
            summary: Scan-Zusammenfassung.
        """
        if self.output_json:
            path = Reporter.save_json(self._results, summary, self.output_json)
            self._write_log(f"[green]{t('log.json_report', path=path)}[/green]")

        if self.output_html:
            path = Reporter.save_html(self._results, summary, self.output_html)
            self._write_log(f"[green]{t('log.html_report', path=path)}[/green]")

    def action_copy_log(self) -> None:
        """Kopiert das Log in die Zwischenablage."""
        if not self._log_lines:
            self.notify(t("notify.log_empty"), severity="warning")
            return

        text = "\n".join(self._log_lines)
        self.copy_to_clipboard(text)
        self.notify(t("notify.log_copied", count=len(self._log_lines)))

    def action_copy_details(self) -> None:
        """Kopiert die Detail-Ansicht (rechter Bereich) in die Zwischenablage."""
        detail = self.query_one("#error-detail", ErrorDetailView)
        if detail._result is None:
            self.notify(t("notify.no_url_selected"), severity="warning")
            return

        rendered = detail.render()
        if isinstance(rendered, Text):
            plain = rendered.plain
        else:
            plain = str(rendered)

        self.copy_to_clipboard(plain)
        self.notify(t("notify.details_copied"))

    def action_show_top_errors(self) -> None:
        """Zeigt den Top-10-Fehler Dialog."""
        if not self._results:
            self.notify(t("notify.no_results"), severity="warning")
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

    def action_show_history(self) -> None:
        """Zeigt die Scan-History und laedt bei Auswahl die Parameter."""
        from .screens.history import HistoryScreen
        self.push_screen(HistoryScreen(), callback=self._on_history_selected)

    def _on_history_selected(self, entry: HistoryEntry | None) -> None:
        """Verarbeitet die Auswahl eines History-Eintrags.

        Uebernimmt alle Parameter des Eintrags und laedt die Sitemap.
        Der Scan wird NICHT automatisch gestartet (User startet mit "s").

        Args:
            entry: Der ausgewaehlte HistoryEntry oder None.
        """
        if entry is None:
            return

        # Parameter uebernehmen
        self.sitemap_url = entry.sitemap_url
        self.concurrency = entry.concurrency
        self.timeout = entry.timeout
        self.console_level = entry.console_level
        self.url_filter = entry.url_filter
        self.user_agent = entry.user_agent
        self.cookies = list(entry.cookies)
        self.accept_consent = entry.accept_consent
        self.trigger_lazy_load = entry.trigger_lazy_load

        # Consent-Binding-Label aktualisieren
        consent_label = t("binding.consent_on") if self.accept_consent else t("binding.consent_off")
        bindings_list = self._bindings.key_to_bindings.get("n", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "toggle_consent":
                self._bindings.key_to_bindings["n"][i] = dataclasses.replace(
                    binding, description=consent_label
                )
                break

        # Scroll-Binding-Label aktualisieren
        scroll_label = t("binding.scroll_on") if self.trigger_lazy_load else t("binding.scroll_off")
        bindings_list = self._bindings.key_to_bindings.get("g", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "toggle_scroll":
                self._bindings.key_to_bindings["g"][i] = dataclasses.replace(
                    binding, description=scroll_label
                )
                break

        # Whitelist neu laden falls sich der Pfad geaendert hat
        old_whitelist_path = self.whitelist_path
        self.whitelist_path = entry.whitelist_path

        if self.whitelist_path and self.whitelist_path != old_whitelist_path:
            try:
                self._whitelist = Whitelist.load(self.whitelist_path)
                self._whitelist_active = True
                self._write_log(f"[green]{t('log.whitelist_loaded', count=len(self._whitelist), path=self.whitelist_path)}[/green]")
            except Exception as e:
                self._write_log(f"[red]{t('log.whitelist_error', error=e)}[/red]")
                self._whitelist = None
                self._whitelist_active = False
        elif not self.whitelist_path:
            self._whitelist = None
            self._whitelist_active = False

        self._write_log(f"[bold]{t('log.history_params')}[/bold]")
        self._write_log(t("log.sitemap_label", url=self.sitemap_url))
        consent_info = t("log.consent_on") if self.accept_consent else t("log.consent_off")
        scroll_info = t("log.scroll_on") if self.trigger_lazy_load else t("log.scroll_off")
        self._write_log(t("log.config", concurrency=self.concurrency, timeout=self.timeout, level=self.console_level, consent=consent_info, scroll=scroll_info))
        if self.cookies:
            cookie_info = ", ".join(c.get("name", "?") for c in self.cookies)
            self._write_log(t("log.cookies_label", cookies=cookie_info))
        if self.url_filter:
            self._write_log(t("log.filter_label", filter=self.url_filter))

        self.refresh_bindings()

        # Sitemap laden (Scan startet User manuell mit "s")
        self._load_sitemap()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Steuert Sichtbarkeit von Bindings.

        Args:
            action: Name der Aktion.
            parameters: Aktionsparameter.

        Returns:
            True wenn sichtbar, None wenn versteckt.
        """
        if action == "toggle_whitelist":
            # Nur anzeigen wenn eine Whitelist geladen wurde
            return True if self._whitelist is not None else None
        if action == "show_history":
            # Nur anzeigen wenn kein Scan und keine Sitemap-Ladung laeuft
            return None if self._scan_running or self._sitemap_loading else True
        if action == "start_scan":
            # Nur anzeigen wenn Sitemap nicht gerade geladen wird
            return None if self._sitemap_loading else True
        return True

    def action_toggle_whitelist(self) -> None:
        """Schaltet die Whitelist um und aktualisiert alle Ergebnisse."""
        self._whitelist_active = not self._whitelist_active

        if self._whitelist_active:
            # Whitelist aktivieren: Patterns erneut anwenden
            total_ignored = 0
            for result in self._results:
                total_ignored += self._whitelist.apply(result)
            ignored_info = t("log.whitelist_ignored_count", count=total_ignored) if total_ignored > 0 else ""
            self._write_log(f"[green]{t('log.whitelist_activated', info=ignored_info)}[/green]")
        else:
            # Whitelist deaktivieren: alle whitelisted-Flags zuruecksetzen
            for result in self._results:
                for error in result.errors:
                    error.whitelisted = False
            self._write_log(f"[yellow]{t('log.whitelist_deactivated')}[/yellow]")

        # Binding-Label aktualisieren (Binding ist frozen -> dataclasses.replace)
        label = t("binding.whitelist_on") if self._whitelist_active else t("binding.whitelist_off")
        bindings_list = self._bindings.key_to_bindings.get("w", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "toggle_whitelist":
                self._bindings.key_to_bindings["w"][i] = dataclasses.replace(
                    binding, description=label
                )
                break

        # UI komplett aktualisieren
        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        summary = self.query_one("#summary", SummaryPanel)
        summary.update_from_results(self._results)

        detail = self.query_one("#error-detail", ErrorDetailView)
        detail.refresh()

        self.refresh_bindings()

    def watch_theme(self, theme_name: str) -> None:
        """Speichert das Theme bei Aenderung persistent.

        Args:
            theme_name: Name des neuen Themes.
        """
        self._settings.theme = theme_name
        self._settings.save()

    def action_toggle_consent(self) -> None:
        """Schaltet die Consent-Akzeptierung um (AN/AUS)."""
        self.accept_consent = not self.accept_consent

        if self.accept_consent:
            self._write_log(f"[green]{t('log.consent_activated')}[/green]")
        else:
            self._write_log(f"[yellow]{t('log.consent_deactivated')}[/yellow]")

        # Binding-Label aktualisieren
        label = t("binding.consent_on") if self.accept_consent else t("binding.consent_off")
        bindings_list = self._bindings.key_to_bindings.get("n", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "toggle_consent":
                self._bindings.key_to_bindings["n"][i] = dataclasses.replace(
                    binding, description=label
                )
                break

        # Einstellung persistent speichern
        self._settings.accept_consent = self.accept_consent
        self._settings.save()

        self.refresh_bindings()

    def action_toggle_scroll(self) -> None:
        """Schaltet das Lazy-Loading-Scrollen um (AN/AUS)."""
        self.trigger_lazy_load = not self.trigger_lazy_load

        if self.trigger_lazy_load:
            self._write_log(f"[green]{t('log.scroll_activated')}[/green]")
        else:
            self._write_log(f"[yellow]{t('log.scroll_deactivated')}[/yellow]")

        # Binding-Label aktualisieren
        label = t("binding.scroll_on") if self.trigger_lazy_load else t("binding.scroll_off")
        bindings_list = self._bindings.key_to_bindings.get("g", [])
        for i, binding in enumerate(bindings_list):
            if binding.action == "toggle_scroll":
                self._bindings.key_to_bindings["g"][i] = dataclasses.replace(
                    binding, description=label
                )
                break

        # Einstellung persistent speichern
        self._settings.trigger_lazy_load = self.trigger_lazy_load
        self._settings.save()

        self.refresh_bindings()

    async def action_quit(self) -> None:
        """Beendet die App und raeumt den Scanner sauber auf."""
        if self._scanner:
            self._scanner.cancel()

            # Playwright-interne Futures werfen TargetClosedError wenn der
            # Browser geschlossen wird waehrend noch Tasks laufen.
            # Diese "fire-and-forget"-Futures kann niemand awaiten,
            # daher unterdruecken wir die Warnung beim Shutdown.
            loop = asyncio.get_running_loop()
            original_handler = loop.get_exception_handler()

            def _suppress_target_closed(the_loop, context):
                exception = context.get("exception")
                if exception is not None:
                    exc_name = type(exception).__name__
                    if exc_name == "TargetClosedError":
                        return
                if original_handler:
                    original_handler(the_loop, context)
                else:
                    the_loop.default_exception_handler(context)

            loop.set_exception_handler(_suppress_target_closed)

            try:
                await self._scanner._cleanup()
            except Exception:
                pass
            self._scanner = None
            self._scan_running = False
        self.exit()

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


_BAR_WIDTH = 20


def _format_progress_bar(current: int, total: int) -> str:
    """Erzeugt einen Unicode-Fortschrittsbalken.

    Args:
        current: Aktuell abgeschlossene Einheiten.
        total: Gesamtanzahl Einheiten.

    Returns:
        String mit gefuellten und leeren Segmenten.
    """
    if total <= 0:
        return "░" * _BAR_WIDTH
    filled = int(_BAR_WIDTH * current / total)
    return "█" * filled + "░" * (_BAR_WIDTH - filled)



def _format_duration(duration_ms: int) -> str:
    """Formatiert eine Dauer in lesbarer Form.

    Unter 60s: "12.3s", ab 60s: "2m 30s", ab 60m: "1h 5m 30s".

    Args:
        duration_ms: Dauer in Millisekunden.

    Returns:
        Formatierter String.
    """
    total_s = duration_ms / 1000
    if total_s < 60:
        return f"{total_s:.1f}s"
    minutes = int(total_s // 60)
    seconds = int(total_s % 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m {seconds}s"


def _sanitize_filename(name: str) -> str:
    """Bereinigt einen String fuer die Verwendung in Dateinamen.

    Entfernt oder ersetzt Zeichen die in Dateinamen nicht erlaubt sind
    (z.B. /, \\, :, *, ?, ", <, >, |).

    Args:
        name: Der zu bereinigende String (z.B. Hostname).

    Returns:
        Sicherer Dateiname-Bestandteil.
    """
    return re.sub(r'[/:*?"<>|\\]', "_", name).strip("_.")


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
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._message = message

    def compose(self) -> ComposeResult:
        """Erstellt das Modal-Layout."""
        from textual.containers import Vertical
        from textual.widgets import Static

        with Vertical():
            yield Static(t("sitemap_error.title"), id="error-title")
            yield Static(self._message, id="error-message")
            yield Static(t("sitemap_error.footer"), id="error-footer")

    def action_close(self) -> None:
        """Schliesst den Dialog."""
        self.dismiss()
