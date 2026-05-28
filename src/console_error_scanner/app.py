"""Hauptanwendung fuer Console Error Scanner."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from rich.markup import escape as escape_markup
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Footer, Header
from textual_themes import THEME_DISPLAY_NAMES, register_all
from textual_widgets import (
    ClickableLinksMixin,
    ContextMenuItem,
    ContextMenuScreen,
    CrashGuard,
    HorizontalSplitter,
    LogPanel,
    LogRouter,
    UrlInputScreen,
    VerticalSplitter,
)

from . import __version__
from .i18n import current_language, t
from .models.history import History, HistoryEntry
from .models.scan_result import PageStatus, ScanResult, ScanSummary
from .models.settings import Settings, parse_cookies
from .models.sitemap import SitemapError, SitemapParser, discover_sitemap, is_local_file, is_sitemap_url
from .models.whitelist import Whitelist
from .services.reporter import Reporter
from .services.scanner import Scanner
from .widgets.preview_panel import PreviewPanel
from .widgets.results_table import ResultsTable
from .widgets.stats_panel import StatsPanel
from .widgets.summary_panel import SummaryHeader


class ConsoleErrorScannerApp(CrashGuard, ClickableLinksMixin, LogRouter, App):
    """TUI-Anwendung zum Scannen von Websites auf Console- und HTTP-Fehler."""

    CSS_PATH = "app.tcss"
    TITLE = f"Console Error Scanner v{__version__}"

    BINDINGS = [
        Binding("q,Q", "quit", "placeholder", key_display="q"),
        # Konvention ueber alle Michael-TUIs: c = Crawl/Scan starten, s = Settings.
        Binding("c,C", "start_scan", "placeholder", key_display="c"),
        Binding("m,M", "load_sitemap_file", "placeholder", key_display="m"),
        Binding("s,S", "show_settings", "placeholder", key_display="s"),
        Binding("h,H", "show_history", "placeholder", key_display="h"),
        Binding("r,R", "save_reports", "placeholder", key_display="r"),
        Binding("w,W", "show_whitelist", "placeholder", key_display="w"),
        Binding("e,E", "toggle_errors", "placeholder", key_display="e"),
        Binding("t,T", "cycle_theme", "placeholder", key_display="t"),
        Binding("l,L", "toggle_log", "placeholder", key_display="l"),
        Binding("d,D", "copy_details", "placeholder", key_display="d"),
        Binding("f10", "show_top_errors", "placeholder", key_display="F10"),
        Binding("slash", "focus_filter", "Filter", key_display="/", show=False),
        Binding("escape", "unfocus_filter", "placeholder", show=False),
        Binding("i,I", "show_about", "placeholder", key_display="i"),
    ]

    # action -> i18n-Schluessel (description + tooltip).
    _BINDING_I18N: dict[str, str] = {
        "quit": "quit",
        "start_scan": "crawl",
        "load_sitemap_file": "load_sitemap",
        "show_settings": "settings",
        "show_history": "history",
        "save_reports": "report",
        "show_whitelist": "whitelist",
        "toggle_errors": "errors_only",
        "cycle_theme": "theme",
        "toggle_log": "log",
        "copy_details": "copy_details",
        "show_top_errors": "top_errors",
        "show_about": "info",
    }

    def __init__(
        self,
        sitemap_url: str = "",
        concurrency: int | None = None,
        timeout: int | None = None,
        output_json: str = "",
        output_html: str = "",
        headless: bool = True,
        url_filter: str = "",
        console_level: str = "",
        user_agent: str = "",
        cookies: list[dict[str, str]] | None = None,
        whitelist_path: str = "",
        accept_consent: bool | None = None,
        trigger_lazy_load: bool | None = None,
    ) -> None:
        super().__init__()

        # Sprache fuer den CrashGuard-Fehlerdialog
        self.crash_guard_lang = current_language()

        # Alle Retro-Themes aus textual-themes registrieren (Ctrl+P → "theme")
        register_all(self)

        # Persistierte Einstellungen laden
        self._settings = Settings.load()

        # CLI ueberschreibt Settings; sonst Settings-Default.
        self.sitemap_url = sitemap_url
        self.concurrency = concurrency if concurrency is not None else self._settings.concurrency
        self.timeout = timeout if timeout is not None else self._settings.timeout
        self.output_json = output_json
        self.output_html = output_html
        # headless: CLI --no-headless erzwingt False; sonst Settings (no_headless invertiert).
        self.headless = headless if not headless else (not self._settings.no_headless)
        self.url_filter = url_filter
        self.console_level = console_level or self._settings.console_level
        self.user_agent = user_agent or self._settings.user_agent
        # Cookies: CLI gewinnt; sonst aus dem Settings-String.
        self.cookies = cookies if cookies else parse_cookies(self._settings.cookies)
        # Whitelist-Pfad: CLI gewinnt, sonst Settings, sonst whitelist.json im CWD.
        self.whitelist_path = whitelist_path or self._settings.whitelist_path
        self.accept_consent = accept_consent if accept_consent is not None else self._settings.accept_consent
        self.trigger_lazy_load = (
            trigger_lazy_load if trigger_lazy_load is not None else self._settings.trigger_lazy_load
        )
        self.show_preview: bool = self._settings.show_preview

        # Theme aus Settings uebernehmen
        self.theme = self._settings.theme

        self._urls: list[str] = []
        self._results: list[ScanResult] = []
        self._scanner: Scanner | None = None
        self._whitelist: Whitelist | None = None
        self._sitemap_loading: bool = False
        self._sitemap_timer: Timer | None = None
        self._sitemap_dots: int = 0
        self._scan_running: bool = False
        self._scan_start_time: float = 0
        self._scan_current: int = 0
        self._scan_total: int = 0
        self._scan_progress_timer: Timer | None = None
        self._preview_service = None  # PreviewService lazy beim ersten Bild

        self._apply_binding_i18n()

    def _apply_binding_i18n(self) -> None:
        """Setzt uebersetzte Description + Tooltip auf jedes Footer-Binding."""
        for bindings_list in self._bindings.key_to_bindings.values():
            for i, binding in enumerate(bindings_list):
                key_i18n = self._BINDING_I18N.get(binding.action)
                if key_i18n is None:
                    continue
                bindings_list[i] = dataclasses.replace(
                    binding,
                    description=t(f"binding.{key_i18n}"),
                    tooltip=t(f"tooltip.{key_i18n}"),
                )

    def compose(self) -> ComposeResult:
        """Erstellt das UI-Layout."""
        yield Header()
        yield SummaryHeader(
            id="summary",
            concurrency=self.concurrency,
            timeout=self.timeout,
            console_level=self.console_level,
            accept_consent=self.accept_consent,
            trigger_lazy_load=self.trigger_lazy_load,
            whitelist_active=bool(self.whitelist_path),
        )

        with Horizontal(id="main-container"):
            with Vertical(id="left-panel"):
                yield ResultsTable(id="results-table")
                yield HorizontalSplitter(target_id="results-table", min_size=5, id="log-splitter")
                yield LogPanel(
                    lang=current_language(),
                    export_name="console-error-scanner",
                    id="scan-log",
                )

            yield VerticalSplitter(target_id="left-panel", min_size=40, id="main-splitter")
            with Vertical(id="right-panel"):
                yield PreviewPanel(id="preview-panel")
                yield HorizontalSplitter(target_id="preview-panel", min_size=5, id="preview-splitter")
                yield StatsPanel(id="stats-panel")

        yield Footer()

    def on_mount(self) -> None:
        """Initialisierung nach dem Starten."""
        # Preview-Panel nur einblenden, wenn die Vorschau aktiviert ist -
        # der Splitter ueber dem StatsPanel verschwindet dann mit.
        with contextlib.suppress(Exception):
            self.query_one("#preview-panel", PreviewPanel).display = self.show_preview
            self.query_one("#preview-splitter", HorizontalSplitter).display = self.show_preview

        # Versionsinfo + Konfiguration ins Log
        self._write_log(f"[bold]{t('log.version', version=__version__)}[/bold]")
        consent_info = t("log.consent_on") if self.accept_consent else t("log.consent_off")
        scroll_info = t("log.scroll_on") if self.trigger_lazy_load else t("log.scroll_off")
        self._write_log(
            t(
                "log.config",
                concurrency=self.concurrency,
                timeout=self.timeout,
                level=self.console_level,
                consent=consent_info,
                scroll=scroll_info,
            )
        )

        # Whitelist laden (wenn angegeben oder whitelist.json im CWD vorhanden)
        if not self.whitelist_path:
            cwd_whitelist = Path("whitelist.json")
            if cwd_whitelist.is_file():
                self.whitelist_path = str(cwd_whitelist)
                self._settings.whitelist_path = self.whitelist_path

        self._load_whitelist_silent()

        # Focus auf die Tabelle setzen
        with contextlib.suppress(Exception):
            from textual.widgets import DataTable

            table = self.query_one("#results-data", DataTable)
            table.focus()

        if self.sitemap_url:
            self._load_sitemap()

    def _load_whitelist_silent(self) -> None:
        """Laedt die Whitelist (oder leert sie) ohne Exceptions hochzuwerfen."""
        if not self.whitelist_path:
            self._whitelist = None
            return
        try:
            self._whitelist = Whitelist.load(self.whitelist_path)
            self._write_log(
                f"[green]{t('log.whitelist_loaded', count=len(self._whitelist), path=self.whitelist_path)}[/green]"
            )
        except Exception as e:
            self._write_log(f"[red]{t('log.whitelist_error', error=e)}[/red]")
            self._whitelist = None

    # --- Sitemap-Loader -----------------------------------------------------

    def _start_sitemap_loading(self) -> None:
        """Startet die Lade-Animation fuer die Sitemap."""
        self._sitemap_loading = True
        self._sitemap_dots = 0
        self._sitemap_start = time.monotonic()
        self.sub_title = t("subtitle.loading_sitemap")
        self.refresh_bindings()
        self._sitemap_timer = self.set_interval(0.5, self._tick_sitemap_loading)

    def _tick_sitemap_loading(self) -> None:
        self._sitemap_dots += 1
        dots = "." * self._sitemap_dots
        self.sub_title = t("subtitle.loading_sitemap_dots", dots=dots)
        # Jede ~3 Sekunden zusaetzlich eine Status-Zeile ins Log -
        # der sub_title oben rechts ist auf vielen Terminals leicht zu uebersehen.
        if self._sitemap_dots > 0 and self._sitemap_dots % 6 == 0:
            elapsed = int(time.monotonic() - self._sitemap_start)
            self._write_log(f"[dim]{t('log.sitemap_still_loading', seconds=elapsed)}[/dim]")

    def _stop_sitemap_loading(self) -> None:
        if self._sitemap_timer is not None:
            self._sitemap_timer.stop()
            self._sitemap_timer = None
        self._sitemap_loading = False
        self._sitemap_dots = 0
        self.refresh_bindings()

    @work(exclusive=True, group="sitemap")
    async def _load_sitemap(self) -> None:
        """Laedt die Sitemap und zeigt die URLs an."""
        self._start_sitemap_loading()

        if is_local_file(self.sitemap_url):
            self._write_log(t("log.loading_local_sitemap", url=self.sitemap_url))
        elif not is_sitemap_url(self.sitemap_url):
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
                self.app.push_screen(_SitemapErrorScreen(t("sitemap_error.sitemap_error", error=e)))
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
            self.app.push_screen(_SitemapErrorScreen(t("sitemap_error.sitemap_error", error=e)))
            return
        except Exception as e:
            self._stop_sitemap_loading()
            self._write_log(f"[red]{t('log.unexpected_error', error=e)}[/red]")
            self.app.push_screen(_SitemapErrorScreen(t("sitemap_error.unexpected_error", error=e)))
            return

        self._stop_sitemap_loading()

        if not self._urls:
            self._write_log(f"[yellow]{t('log.no_urls_in_sitemap')}[/yellow]")
            self.notify(t("notify.no_urls"), severity="warning")
            return

        self._write_log(f"[green]{t('log.urls_loaded', count=len(self._urls))}[/green]")

        self._results = [ScanResult(url=url) for url in self._urls]

        summary = self.query_one("#summary", SummaryHeader)
        summary.set_sitemap(self.link_markup(self.sitemap_url, self.sitemap_url), len(self._urls))

        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        self.sub_title = t("subtitle.urls_count", count=len(self._urls))

        # Auto-Scan starten wenn CLI-Reports angefordert
        if self.output_json or self.output_html:
            self.action_start_scan()

    # --- Scan ---------------------------------------------------------------

    def action_start_scan(self) -> None:
        """Startet einen neuen Scan. Ohne Sitemap-URL erst URL abfragen."""
        if self._scan_running:
            self.notify(t("notify.scan_running"), severity="warning")
            return
        if self._urls:
            self._run_scan()
            return
        # Keine URLs geladen → URL abfragen, dann Sitemap laden
        self.push_screen(
            UrlInputScreen(
                initial=self.sitemap_url,
                lang=current_language(),
                title=t("url_input.title"),
                prompt=t("url_input.prompt"),
                placeholder=t("url_input.placeholder"),
            ),
            callback=self._on_url_entered,
        )

    def _on_url_entered(self, url: str | None) -> None:
        """Callback des URL-Dialogs: uebernimmt URL und laedt die Sitemap."""
        if url is None:
            return
        self.sitemap_url = url
        self.sub_title = url
        self._load_sitemap()

    def action_load_sitemap_file(self) -> None:
        """Oeffnet einen File-Open-Dialog (textual-fspicker) zur Sitemap-Auswahl."""
        if self._scan_running or self._sitemap_loading:
            self.notify(t("notify.scan_running"), severity="warning")
            return
        from textual_fspicker import FileOpen, Filters

        self.push_screen(
            FileOpen(
                location=str(Path.cwd()),
                title=t("file_picker.title"),
                open_button=t("file_picker.open_button"),
                cancel_button=t("file_picker.cancel_button"),
                filters=Filters(
                    (t("file_picker.filter_xml"), lambda p: p.suffix.lower() == ".xml"),
                    (t("file_picker.filter_all"), lambda p: True),
                ),
            ),
            callback=self._on_sitemap_file_chosen,
        )

    def _on_sitemap_file_chosen(self, path: Path | None) -> None:
        """Callback des File-Picker-Dialogs: uebernimmt Datei und laedt die Sitemap."""
        if path is None:
            return
        self.sitemap_url = str(path)
        self.sub_title = path.name
        self._load_sitemap()

    @work(exclusive=True, group="scan")
    async def _run_scan(self) -> None:
        """Fuehrt den eigentlichen Scan aller URLs aus."""
        if self._scan_running:
            return
        if not self._urls:
            self.notify(t("notify.no_urls_loaded"), severity="error")
            return

        self._scan_running = True
        self._scan_start_time = time.monotonic()
        self._scan_current = 0
        self._scan_total = len(self._results)
        self._scan_progress_timer = self.set_interval(0.5, self._tick_scan_progress)

        # Laufende Preview-Worker abbrechen + Panel leeren - das Sidecar-
        # Browser-Tab darf nicht parallel zum Scan rendern (kostet CPU/RAM
        # und macht ohnehin keinen Sinn waehrend der Cursor durch alle
        # Zeilen wandert).
        for worker in list(self.workers):
            if getattr(worker, "group", None) == "preview":
                worker.cancel()
        with contextlib.suppress(Exception):
            self.query_one("#preview-panel", PreviewPanel).clear()

        # Log-Panel einblenden + leeren
        log_panel = self.query_one("#scan-log", LogPanel)
        log_panel.show()
        log_panel.clear_log()
        self.query_one("#log-splitter", HorizontalSplitter).remove_class("hidden")

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

        # History-Eintrag speichern
        with contextlib.suppress(Exception):
            History.add(
                HistoryEntry(
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
            )
            self._write_log(f"[dim]{t('log.history_updated')}[/dim]")

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

        def on_result(result: ScanResult) -> None:
            self._on_scan_result(result)

        def on_log(msg: str) -> None:
            self._write_log(msg)

        def on_progress(current: int, total: int) -> None:
            self._scan_current = current
            self._scan_total = total

        try:
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

        duration_ms = int((time.monotonic() - self._scan_start_time) * 1000)
        duration_text = _format_duration(duration_ms)
        summary_data = ScanSummary.from_results(self.sitemap_url, self._results, duration_ms)

        self._write_log(f"\n[bold green]{t('log.scan_complete', duration=duration_text)}[/bold green]")
        ignored_info = f" | Ignored: {summary_data.total_ignored}" if summary_data.total_ignored > 0 else ""
        self._write_log(
            t(
                "log.scan_result",
                errors_pages=summary_data.urls_with_errors,
                console=summary_data.total_console_errors,
                http_404=summary_data.total_http_404,
                http_4xx=summary_data.total_http_4xx,
                http_5xx=summary_data.total_http_5xx,
                ignored=ignored_info,
            )
        )
        if summary_data.total_ignored > 0:
            self._write_log(f"[dim]{t('log.whitelist_suppressed', count=summary_data.total_ignored)}[/dim]")

        # Tabelle final aktualisieren
        table = self.query_one("#results-table", ResultsTable)
        table.load_results(self._results)

        # Summary aktualisieren
        summary = self.query_one("#summary", SummaryHeader)
        summary.update_from_results(self._results, duration_text=duration_text)

        self.sub_title = t("subtitle.scan_complete", count=len(self._urls))

        # Jetzt erst Preview fuer die aktuell markierte Zeile nachladen -
        # vorher (waehrend des Scans) war das Auto-Scroll-Cursor-Springen
        # nicht sinnvoll als Preview-Trigger.
        if self.show_preview:
            self._refresh_preview_for_cursor()

        if self.output_json or self.output_html:
            self._save_reports_auto(summary_data)

    def _on_scan_result(self, result: ScanResult) -> None:
        """Verarbeitet ein einzelnes Scan-Ergebnis (Live-Update)."""
        if self._whitelist is not None:
            self._whitelist.apply(result)

        table = self.query_one("#results-table", ResultsTable)
        table.update_result(result)

        summary = self.query_one("#summary", SummaryHeader)
        summary.update_from_results(self._results)

        stats = self.query_one("#stats-panel", StatsPanel)
        if stats.selected_result() is result:
            stats.refresh_view()

    def _tick_scan_progress(self) -> None:
        """Aktualisiert den Fortschrittsbalken im Header."""
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
                bar=bar,
                pct=pct,
                current=current,
                total=total,
                remaining=remaining,
                avg=f"{avg_per_url:.1f}",
            )
        else:
            self.sub_title = t("subtitle.scanning_start", bar=bar, total=total)

    # --- Tabellen-Events ----------------------------------------------------

    def on_results_table_result_highlighted(self, event: ResultsTable.ResultHighlighted) -> None:
        stats = self.query_one("#stats-panel", StatsPanel)
        stats.show_result(event.result)
        if self.show_preview and not self._scan_running:
            self._load_preview(event.result.url)

    def on_results_table_result_selected(self, event: ResultsTable.ResultSelected) -> None:
        from .screens.error_detail import ErrorDetailScreen

        self.push_screen(ErrorDetailScreen(event.result))

    def on_results_table_context_requested(self, event: ResultsTable.ContextRequested) -> None:
        """Rechtsklick auf Tabellenzeile → Kontextmenue oeffnen."""
        table = self.query_one("#results-table", ResultsTable)
        # Filter-Toggle-Label dynamisch: je nach aktuellem Zustand
        # "Nur Fehler anzeigen" oder "Alle anzeigen".
        filter_label = t("ctx.show_all") if table._show_only_errors else t("ctx.show_errors_only")
        items = [
            ContextMenuItem("open", t("ctx.open_url")),
            ContextMenuItem("copy_url", t("ctx.copy_url")),
            ContextMenuItem.separator(),
            ContextMenuItem("details", t("ctx.show_details")),
            ContextMenuItem("copy_details", t("ctx.copy_details")),
            ContextMenuItem.separator(),
            ContextMenuItem("rescan", t("ctx.rescan"), enabled=not self._scan_running),
            ContextMenuItem.separator(),
            ContextMenuItem("toggle_errors", filter_label),
        ]
        self._ctx_result = event.result
        self.push_screen(
            ContextMenuScreen(items, at=(event.screen_x, event.screen_y)),
            callback=self._on_results_menu,
        )

    def _on_results_menu(self, choice: str | None) -> None:
        """Verarbeitet die Auswahl aus dem Tabellen-Kontextmenue."""
        result = getattr(self, "_ctx_result", None)
        self._ctx_result = None
        if choice is None or result is None:
            return

        if choice == "open":
            import webbrowser

            with contextlib.suppress(Exception):
                webbrowser.open(result.url)
        elif choice == "copy_url":
            self.copy_to_clipboard(result.url)
            self.notify(t("ctx.url_copied"))
        elif choice == "details":
            from .screens.error_detail import ErrorDetailScreen

            self.push_screen(ErrorDetailScreen(result))
        elif choice == "copy_details":
            # Selected-Result kurz setzen, dann action_copy_details rufen
            stats = self.query_one("#stats-panel", StatsPanel)
            stats.show_result(result)
            self.action_copy_details()
        elif choice == "rescan":
            self._rescan_single(result)
        elif choice == "toggle_errors":
            self.action_toggle_errors()

    @work(exclusive=False, group="rescan")
    async def _rescan_single(self, result: ScanResult) -> None:
        """Scannt EINE einzelne URL erneut, ohne den ganzen Lauf neu zu starten.

        Verwendet die aktuellen Settings (Konkurrenz egal, da nur 1 URL).
        Wenn gerade ein voller Scan laeuft, wird der Rescan abgelehnt — der
        gemeinsame Browser-Sidecar wuerde sonst zwei parallele Welten haben.
        """
        if self._scan_running:
            self.notify(t("ctx.rescan_busy"), severity="warning")
            return

        self._write_log(f"[dim]{t('ctx.rescanning', url=self.link_markup(result.url, result.url))}[/dim]")

        # Result zuruecksetzen, damit die Tabelle "pending"-Spinner zeigt
        result.status = PageStatus.PENDING
        result.http_status_code = 0
        result.load_time_ms = 0
        result.page_size_bytes = 0
        result.errors.clear()
        result.retry_count = 0
        result.response_headers = {}
        result.content_type = ""
        result.last_modified = ""

        table = self.query_one("#results-table", ResultsTable)
        table.update_result(result)

        # Single-Result-Scan ueber einen frischen Scanner mit concurrency=1.
        scanner = Scanner(
            concurrency=1,
            timeout=self.timeout,
            headless=self.headless,
            console_level=self.console_level,
            user_agent=self.user_agent,
            cookies=self.cookies,
            accept_consent=self.accept_consent,
            trigger_lazy_load=self.trigger_lazy_load,
        )

        def on_result(updated: ScanResult) -> None:
            # Whitelist nachziehen, dann Tabelle + Detail + Summary updaten
            if self._whitelist is not None:
                self._whitelist.apply(updated)
            table.update_result(updated)
            stats = self.query_one("#stats-panel", StatsPanel)
            if stats.selected_result() is updated:
                stats.refresh_view()
            summary = self.query_one("#summary", SummaryHeader)
            summary.update_from_results(self._results)

        try:
            await scanner.scan_urls(
                [result],
                on_result=on_result,
                on_log=self._write_log,
            )
        except Exception as exc:
            self._write_log(f"[red]{t('notify.scan_error', error=exc)}[/red]")
            self.notify(t("notify.scan_error", error=exc), severity="error")
        finally:
            with contextlib.suppress(Exception):
                await scanner._cleanup()

    # --- Preview-Sidecar ----------------------------------------------------

    def _refresh_preview_for_cursor(self) -> None:
        """Loest fuer die aktuell markierte Zeile das Vorschau-Bild aus."""
        if not self.show_preview:
            return
        with contextlib.suppress(Exception):
            table = self.query_one("#results-table", ResultsTable)
            result = table.get_selected_result()
            if result is not None:
                self._load_preview(result.url)

    @work(exclusive=True, group="preview")
    async def _load_preview(self, url: str) -> None:
        """Laedt im Hintergrund einen Screenshot und zeigt ihn im Panel."""
        from .services.preview_service import PreviewService

        panel = self.query_one("#preview-panel", PreviewPanel)
        panel.show_loading(url)
        if self._preview_service is None:
            self._preview_service = PreviewService()
        data = await self._preview_service.capture(url)
        # Cursor kann zwischenzeitlich weitergewandert sein - nur anzeigen,
        # wenn dieser Worker noch zur aktuellen URL gehoert.
        if panel.current_url() == url or panel.current_url() == "":
            panel.show_preview(data, url=url)

    def action_toggle_stats_headers(self) -> None:
        """Klick auf den HTTP-Header-Panel-Titel im StatsPanel → ein-/ausklappen."""
        with contextlib.suppress(Exception):
            self.query_one("#stats-panel", StatsPanel).toggle_headers()

    def on_preview_panel_copy_requested(self, event: PreviewPanel.CopyRequested) -> None:
        """Rechtsklick auf das Vorschau-Bild → direkt in Zwischenablage kopieren."""
        self._copy_preview_to_clipboard()

    def on_preview_panel_save_requested(self, event: PreviewPanel.SaveRequested) -> None:
        """Shift + Rechtsklick → Bild als PNG-Datei speichern."""
        self._save_preview_to_disk()

    def _copy_preview_to_clipboard(self) -> None:
        """Kopiert das aktuelle Vorschau-Bild in die OS-Zwischenablage."""
        from .services.image_clipboard import copy_png_to_clipboard

        panel = self.query_one("#preview-panel", PreviewPanel)
        png = panel.current_png()
        if png is None:
            self.notify(t("preview.no_image"), severity="warning")
            return
        try:
            copy_png_to_clipboard(png)
        except Exception as exc:
            self.notify(t("preview.copy_failed", error=exc), severity="error")
            return
        self.notify(t("preview.copied"))

    def _save_preview_to_disk(self) -> None:
        """Speichert das aktuelle Vorschau-Bild als PNG neben den Reports."""
        panel = self.query_one("#preview-panel", PreviewPanel)
        png = panel.current_png()
        url = panel.current_url()
        if png is None or not url:
            self.notify(t("preview.no_image"), severity="warning")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        host = _sanitize_filename(urlparse(url).hostname or "page")
        path = Path(f"preview_{host}_{timestamp}.png")
        try:
            path.write_bytes(png)
        except Exception as exc:
            self.notify(t("preview.copy_failed", error=exc), severity="error")
            return
        self._write_log(f"[green]{t('preview.saved', path=self.link_markup(str(path), str(path)))}[/green]")
        self.notify(t("preview.saved", path=str(path)))

    async def on_unmount(self) -> None:
        """Beendet den Preview-Sidecar sauber.

        Reihenfolge: erst laufende Preview-Worker abbrechen, dann
        Browser/Playwright schliessen. Sonst feuert ein in-flight
        page.goto noch nach dem Browser-Close ein net::ERR_ABORTED
        als unbehandelte Future-Exception.
        """
        cancelled_preview = False
        for worker in list(self.workers):
            if getattr(worker, "group", None) == "preview":
                worker.cancel()
                cancelled_preview = True
        if cancelled_preview:
            await asyncio.sleep(0.2)
        if self._preview_service is not None:
            await self._preview_service.close()

    # --- Reports / Top 10 / Whitelist Viewer -------------------------------

    def action_save_reports(self) -> None:
        """Speichert HTML- und JSON-Reports."""
        if not self._results:
            self.notify(t("notify.no_results"), severity="warning")
            return

        scanned = [r for r in self._results if r.status not in (PageStatus.PENDING, PageStatus.SCANNING)]
        if not scanned:
            self.notify(t("notify.not_scanned"), severity="warning")
            return

        duration_ms = int((time.monotonic() - self._scan_start_time) * 1000) if self._scan_start_time > 0 else 0
        summary = ScanSummary.from_results(self.sitemap_url, self._results, duration_ms)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        site_name = _sanitize_filename(urlparse(self.sitemap_url).hostname or "unknown")
        base_name = f"console-error-report_{site_name}_{timestamp}"

        json_path = f"{base_name}.json"
        saved_json = Reporter.save_json(self._results, summary, json_path)
        self._write_log(f"[green]{t('log.json_report', path=self.link_markup(saved_json, saved_json))}[/green]")

        html_path = f"{base_name}.html"
        saved_html = Reporter.save_html(self._results, summary, html_path)
        self._write_log(f"[green]{t('log.html_report', path=self.link_markup(saved_html, saved_html))}[/green]")

        self.notify(t("notify.reports_saved", json_path=json_path, html_path=html_path))

    def _save_reports_auto(self, summary: ScanSummary) -> None:
        """Speichert Reports automatisch (CLI-Parameter)."""
        if self.output_json:
            path = Reporter.save_json(self._results, summary, self.output_json)
            self._write_log(f"[green]{t('log.json_report', path=self.link_markup(path, path))}[/green]")
        if self.output_html:
            path = Reporter.save_html(self._results, summary, self.output_html)
            self._write_log(f"[green]{t('log.html_report', path=self.link_markup(path, path))}[/green]")

    def action_copy_details(self) -> None:
        """Kopiert die Detail-Ansicht (rechter Bereich) in die Zwischenablage."""
        stats = self.query_one("#stats-panel", StatsPanel)
        result = stats.selected_result()
        if result is None:
            self.notify(t("notify.no_url_selected"), severity="warning")
            return

        # Plain-Text-Variante der wichtigsten Felder fuer die Zwischenablage.
        lines = [
            f"URL: {result.url}",
            f"Status: {result.status_icon} {result.status.value}",
            f"HTTP: {result.http_status_code if result.http_status_code else '-'}",
            f"Ladezeit: {result.load_time_ms}ms",
            f"Groesse: {result.page_size_bytes} bytes",
        ]
        if result.content_type:
            lines.append(f"Content-Type: {result.content_type}")
        if result.last_modified:
            lines.append(f"Last-Modified: {result.last_modified}")
        if result.retry_count > 0:
            lines.append(f"Retries: {result.retry_count}")

        active_errors = [e for e in result.errors if not e.whitelisted]
        if active_errors:
            lines.append("")
            lines.append(f"Fehler/Warnungen ({len(active_errors)}):")
            for idx, err in enumerate(active_errors, 1):
                tag = err.error_type.value.upper()
                lines.append(f"  {idx}. [{tag}] {err.message}")
                if err.source:
                    src = err.source + (f":{err.line_number}" if err.line_number else "")
                    lines.append(f"     Quelle: {src}")

        ignored = [e for e in result.errors if e.whitelisted]
        if ignored:
            lines.append("")
            lines.append(f"Whitelist ({len(ignored)}):")
            for idx, err in enumerate(ignored, 1):
                lines.append(f"  {idx}. [{err.error_type.value.upper()}] {err.message}")

        self.copy_to_clipboard("\n".join(lines))
        self.notify(t("notify.details_copied"))

    def action_show_top_errors(self) -> None:
        """Zeigt den Top-10-Fehler Dialog."""
        if not self._results:
            self.notify(t("notify.no_results_for_top"), severity="warning")
            return
        from .screens.top_errors import TopErrorsScreen

        self.push_screen(TopErrorsScreen(self._results))

    def action_show_whitelist(self) -> None:
        """Zeigt die geladenen Whitelist-Patterns."""
        from .screens.whitelist import WhitelistScreen

        if self._whitelist is None:
            self.notify(t("notify.no_whitelist"), severity="warning")
        self.push_screen(WhitelistScreen(self._whitelist, self._results))

    # --- Log / Filter -------------------------------------------------------

    def action_toggle_log(self) -> None:
        """Blendet das LogPanel (samt Splitter) ein/aus."""
        log_panel = self.query_one("#scan-log", LogPanel)
        log_panel.toggle()
        self.query_one("#log-splitter", HorizontalSplitter).set_class(log_panel.has_class("-log-hidden"), "hidden")

    def on_log_panel_hidden(self, event: LogPanel.Hidden) -> None:
        """Log per Kontextmenue ausgeblendet — Splitter mit ausblenden."""
        self.query_one("#log-splitter", HorizontalSplitter).add_class("hidden")

    def action_toggle_errors(self) -> None:
        """Wechselt zwischen alle/nur Fehler in der Tabelle."""
        if not self._results:
            self.notify(t("notify.no_results"), severity="warning")
            return
        table = self.query_one("#results-table", ResultsTable)
        active = table.toggle_error_filter()

        new_label = t("binding.errors_show_all") if active else t("binding.errors_only")
        for i, b in enumerate(self._bindings.key_to_bindings.get("e", [])):
            if b.action == "toggle_errors":
                self._bindings.key_to_bindings["e"][i] = dataclasses.replace(b, description=new_label)
        for i, b in enumerate(self._bindings.key_to_bindings.get("E", [])):
            if b.action == "toggle_errors":
                self._bindings.key_to_bindings["E"][i] = dataclasses.replace(b, description=new_label)
        self.refresh_bindings()

    def action_focus_filter(self) -> None:
        """Fokussiert das Filter-Eingabefeld."""
        with contextlib.suppress(Exception):
            from textual.widgets import Input

            filter_input = self.query_one("#filter-bar", Input)
            filter_input.focus()

    def action_unfocus_filter(self) -> None:
        """Leert den Filter und gibt Focus zurueck an die Tabelle."""
        with contextlib.suppress(Exception):
            from textual.widgets import DataTable, Input

            filter_input = self.query_one("#filter-bar", Input)
            filter_input.value = ""
            table = self.query_one("#results-data", DataTable)
            table.focus()

    # --- About / Settings / History / Theme --------------------------------

    def action_show_about(self) -> None:
        """Zeigt den standardisierten About-Dialog aus textual-widgets an."""
        from textual_widgets import AboutScreen

        from . import __author__, __year__

        self.push_screen(
            AboutScreen(
                app_name="Console Error Scanner",
                version=__version__,
                author=__author__,
                release=__year__,
                description=t("about.description"),
                lang=current_language(),
                license="Apache-2.0",
                url="https://github.com/michaelblaess/console-error-scanner",
            )
        )

    def action_show_settings(self) -> None:
        """Oeffnet den Einstellungs-Dialog (BaseSettingsScreen)."""
        from .screens.settings import ScannerSettingsScreen

        current: dict[str, object] = {
            "language": self._settings.language,
            "accept_consent": self._settings.accept_consent,
            "trigger_lazy_load": self._settings.trigger_lazy_load,
            "concurrency": self._settings.concurrency,
            "timeout": self._settings.timeout,
            "console_level": self._settings.console_level,
            "show_preview": self._settings.show_preview,
            "no_headless": self._settings.no_headless,
            "user_agent": self._settings.user_agent,
            "cookies": self._settings.cookies,
            "whitelist_path": self._settings.whitelist_path,
        }
        self.push_screen(
            ScannerSettingsScreen(current, lang=current_language()),
            callback=self._on_settings_closed,
        )

    def _on_settings_closed(self, result: dict[str, object] | None) -> None:
        """Uebernimmt die geaenderten Settings und persistiert sie.

        Schreibt fuer jedes tatsaechlich geaenderte Feld eine
        ``Label: alt → neu``-Zeile ins Log. Wenn nichts geaendert wurde,
        steht NUR die Hinweiszeile ``Einstellungen unveraendert`` da.
        """
        if result is None:
            return

        # Old-Snapshot fuer das Diff-Logging
        old_snapshot = {
            "language": self._settings.language,
            "accept_consent": self._settings.accept_consent,
            "trigger_lazy_load": self._settings.trigger_lazy_load,
            "concurrency": self._settings.concurrency,
            "timeout": self._settings.timeout,
            "console_level": self._settings.console_level,
            "show_preview": self._settings.show_preview,
            "no_headless": self._settings.no_headless,
            "user_agent": self._settings.user_agent,
            "cookies": self._settings.cookies,
            "whitelist_path": self._settings.whitelist_path,
        }

        old_whitelist_path = self._settings.whitelist_path

        self._settings.language = str(result.get("language", self._settings.language))
        self._settings.accept_consent = bool(result.get("accept_consent", self._settings.accept_consent))
        self._settings.trigger_lazy_load = bool(result.get("trigger_lazy_load", self._settings.trigger_lazy_load))
        self._settings.concurrency = int(result.get("concurrency", self._settings.concurrency))  # type: ignore[arg-type]
        self._settings.timeout = int(result.get("timeout", self._settings.timeout))  # type: ignore[arg-type]
        self._settings.console_level = str(result.get("console_level", self._settings.console_level))
        self._settings.show_preview = bool(result.get("show_preview", self._settings.show_preview))
        self._settings.no_headless = bool(result.get("no_headless", self._settings.no_headless))
        self._settings.user_agent = str(result.get("user_agent", self._settings.user_agent))
        self._settings.cookies = str(result.get("cookies", self._settings.cookies))
        self._settings.whitelist_path = str(result.get("whitelist_path", self._settings.whitelist_path))
        self._settings.save()

        # Runtime-Werte fuer den naechsten Scan aktualisieren
        self.accept_consent = self._settings.accept_consent
        self.trigger_lazy_load = self._settings.trigger_lazy_load
        self.concurrency = self._settings.concurrency
        self.timeout = self._settings.timeout
        self.console_level = self._settings.console_level
        self.show_preview = self._settings.show_preview
        self.headless = not self._settings.no_headless
        self.user_agent = self._settings.user_agent
        self.cookies = parse_cookies(self._settings.cookies)

        # Preview-Panel zur Laufzeit ein-/ausblenden
        with contextlib.suppress(Exception):
            self.query_one("#preview-panel", PreviewPanel).display = self.show_preview
            self.query_one("#preview-splitter", HorizontalSplitter).display = self.show_preview
            if self.show_preview:
                self._refresh_preview_for_cursor()

        # Diff-Log: pro geaendertem Feld eine Zeile
        diff_fields = [
            ("language", t("binding.settings") + " (Lang)"),
            ("accept_consent", t("settings.consent_label")),
            ("trigger_lazy_load", t("settings.scroll_label")),
            ("concurrency", t("settings.concurrency_label")),
            ("timeout", t("settings.timeout_label")),
            ("console_level", t("settings.console_level_label")),
            ("show_preview", t("settings.preview_label")),
            ("no_headless", t("settings.headless_label")),
            ("user_agent", t("settings.user_agent_label")),
            ("cookies", t("settings.cookies_label")),
            ("whitelist_path", t("settings.whitelist_label")),
        ]
        changes_logged = 0
        for key, label in diff_fields:
            old_val = old_snapshot[key]
            new_val = getattr(self._settings, key)
            if old_val == new_val:
                continue
            self._write_log(
                f"[green]{t('log.setting_changed', label=label, old=_fmt_setting(old_val), new=_fmt_setting(new_val))}[/green]"
            )
            changes_logged += 1
        if changes_logged == 0:
            self._write_log(f"[dim]{t('log.no_settings_changed')}[/dim]")

        # Whitelist-Pfad geaendert?
        if self._settings.whitelist_path != old_whitelist_path:
            self.whitelist_path = self._settings.whitelist_path
            if self.whitelist_path:
                self._load_whitelist_silent()
                if self._whitelist is not None and self._results:
                    for result_item in self._results:
                        self._whitelist.apply(result_item)
                    self._write_log(f"[green]{t('log.whitelist_reloaded', count=len(self._whitelist))}[/green]")
            else:
                self._whitelist = None
                for result_item in self._results:
                    for error in result_item.errors:
                        error.whitelisted = False
                self._write_log(f"[yellow]{t('log.whitelist_cleared')}[/yellow]")

            # Tabelle + Detail + Summary neu zeichnen
            with contextlib.suppress(Exception):
                table = self.query_one("#results-table", ResultsTable)
                table.load_results(self._results)
            with contextlib.suppress(Exception):
                self.query_one("#stats-panel", StatsPanel).refresh_view()

        # Header mit aktuellen Konfig-Werten aktualisieren
        with contextlib.suppress(Exception):
            header = self.query_one("#summary", SummaryHeader)
            header.update_config(
                self.concurrency,
                self.timeout,
                self.console_level,
                self.accept_consent,
                self.trigger_lazy_load,
            )
            header.update_from_results(self._results)

    def action_show_history(self) -> None:
        """Zeigt die Scan-History und uebernimmt bei Auswahl die URL."""
        from .screens.history import HistoryScreen

        self.push_screen(HistoryScreen(), callback=self._on_history_selected)

    def _on_history_selected(self, entry: HistoryEntry | None) -> None:
        """Uebernimmt nur die URL aus dem History-Eintrag — Scan-Parameter
        kommen weiterhin aus den aktuellen Einstellungen (Settings).

        Analog zum Sitemap-Tracker: History ist eine URL-Liste, kein
        Settings-Override.
        """
        if entry is None:
            return

        self.sitemap_url = entry.sitemap_url
        self.sub_title = self.sitemap_url
        self._write_log(
            t(
                "log.history_params",
            )
        )
        self._write_log(t("log.sitemap_label", url=self.link_markup(self.sitemap_url, self.sitemap_url)))

        # Sitemap laden (Scan startet User manuell mit "s")
        self._load_sitemap()

    def action_cycle_theme(self) -> None:
        """Wechselt zum naechsten Retro-Theme (alphabetisch sortiert)."""
        names = sorted(self.available_themes.keys())
        if not names:
            return
        try:
            idx = names.index(self.theme)
        except ValueError:
            idx = -1
        next_theme = names[(idx + 1) % len(names)]
        self.theme = next_theme
        display = THEME_DISPLAY_NAMES.get(next_theme, next_theme)
        self.notify(t("notify.theme", name=display))

    def watch_theme(self, theme_name: str) -> None:
        """Persistiert jede Theme-Aenderung (auch via Ctrl+P)."""
        if not hasattr(self, "_settings"):
            return
        if self._settings.theme == theme_name:
            return
        self._settings.theme = theme_name
        self._settings.save()

    # --- check_action -------------------------------------------------------

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Steuert Sichtbarkeit von Bindings."""
        if action == "start_scan":
            return None if self._sitemap_loading else True
        if action == "load_sitemap_file":
            return None if self._scan_running or self._sitemap_loading else True
        if action == "show_history":
            return None if self._scan_running or self._sitemap_loading else True
        if action in ("save_reports", "show_top_errors", "toggle_errors", "copy_details"):
            return True if self._results else None
        if action == "show_whitelist":
            return True if self._whitelist is not None else None
        return True

    # --- Quit ---------------------------------------------------------------

    async def action_quit(self) -> None:
        """Beendet die App und raeumt den Scanner sauber auf."""
        if self._scanner:
            self._scanner.cancel()

            # Playwright TargetClosedError beim Shutdown unterdruecken
            loop = asyncio.get_running_loop()
            original_handler = loop.get_exception_handler()

            def _suppress_target_closed(the_loop, context):
                exception = context.get("exception")
                if exception is not None and type(exception).__name__ == "TargetClosedError":
                    return
                if original_handler:
                    original_handler(the_loop, context)
                else:
                    the_loop.default_exception_handler(context)

            loop.set_exception_handler(_suppress_target_closed)

            with contextlib.suppress(Exception):
                await self._scanner._cleanup()
            self._scanner = None
            self._scan_running = False
        self.exit()

    # --- Logging-Bridge -----------------------------------------------------

    def _write_log(self, line: str) -> None:
        """Schreibt eine Zeile ins LogPanel mit auto-verlinkten URLs."""
        with contextlib.suppress(Exception):
            self.query_one("#scan-log", LogPanel).write_log(self.linkify_urls(line))


_BAR_WIDTH = 20


def _format_progress_bar(current: int, total: int) -> str:
    """Erzeugt einen Unicode-Fortschrittsbalken."""
    if total <= 0:
        return "░" * _BAR_WIDTH
    filled = int(_BAR_WIDTH * current / total)
    return "█" * filled + "░" * (_BAR_WIDTH - filled)


def _format_duration(duration_ms: int) -> str:
    """Formatiert eine Dauer in lesbarer Form."""
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


def _fmt_setting(value: object) -> str:
    """Formatiert einen Settings-Wert kompakt fuers Log-Diff."""
    if isinstance(value, bool):
        return "AN" if value else "AUS"
    if value is None or value == "":
        return "—"
    text = str(value)
    if len(text) > 40:
        return text[:37] + "…"
    return text


def _sanitize_filename(name: str) -> str:
    """Bereinigt einen String fuer Dateinamen."""
    return re.sub(r'[/:*?"<>|\\]', "_", name).strip("_.")


class _SitemapErrorScreen(ModalScreen):
    """Modal-Dialog fuer Sitemap-Fehler."""

    DEFAULT_CSS = """
    _SitemapErrorScreen {
        align: center middle;
    }

    _SitemapErrorScreen > Vertical {
        width: 80%;
        max-width: 90;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    _SitemapErrorScreen #error-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $error;
        color: auto;
        margin-bottom: 1;
    }

    _SitemapErrorScreen #error-message {
        height: auto;
        padding: 1;
    }

    _SitemapErrorScreen #error-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    _SitemapErrorScreen #error-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q,Q", "close", "Close"),
    ]

    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._message = message

    def compose(self) -> ComposeResult:
        from textual.widgets import Static

        # URLs in der Fehlermeldung Hover-klickbar machen. Markup-Sonderzeichen
        # in der Meldung zuerst escapen, dann linkify - sonst frisst Rich
        # eckige Klammern als Tag und der Link wird unsichtbar.
        linkify = getattr(self.app, "linkify_urls", None)
        body = escape_markup(self._message)
        if callable(linkify):
            body = linkify(body)

        with Vertical():
            yield Static(t("sitemap_error.title"), id="error-title")
            yield Static(body, id="error-message", markup=True)
            with Horizontal(id="error-buttons"):
                yield Button(t("binding.close"), variant="primary", id="error-close")

    @on(Button.Pressed, "#error-close")
    def _on_close_button(self) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
