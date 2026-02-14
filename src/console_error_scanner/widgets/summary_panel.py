"""Summary-Widget mit Zaehler und Uebersicht."""

from __future__ import annotations

from rich.text import Text
from textual.app import RenderResult
from textual.widget import Widget

from ..models.scan_result import ScanResult, ScanSummary, PageStatus


class SummaryPanel(Widget):
    """Zeigt eine Zusammenfassung des Scan-Fortschritts."""

    DEFAULT_CSS = """
    SummaryPanel {
        height: auto;
        min-height: 3;
        padding: 0 1;
        background: $surface;
        border-bottom: solid $accent;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._sitemap_url: str = ""
        self._total_urls: int = 0
        self._scanned: int = 0
        self._console_errors: int = 0
        self._console_warnings: int = 0
        self._http_404: int = 0
        self._http_4xx: int = 0
        self._http_5xx: int = 0
        self._timeouts: int = 0
        self._ignored: int = 0
        self._urls_with_errors: int = 0

    def render(self) -> RenderResult:
        """Rendert die Zusammenfassung."""
        text = Text()

        if not self._sitemap_url:
            return Text("Keine Sitemap geladen.", style="dim italic")

        # Zeile 1: Sitemap + Fortschritt
        text.append(" Sitemap: ", style="bold")
        text.append(self._sitemap_url, style="dim")
        text.append("  |  ", style="dim")
        text.append(f"{self._total_urls} URLs", style="bold")

        if self._scanned > 0:
            text.append(f"  ({self._scanned}/{self._total_urls} gescannt)", style="dim")

        # Zeile 2: Fehler-Zaehler
        text.append("\n")

        if self._scanned > 0:
            if self._urls_with_errors > 0:
                text.append(f" {self._urls_with_errors} Seiten mit Fehlern", style="bold red")
            else:
                text.append(" Keine Fehler gefunden", style="bold green")

            text.append("  |  ")
            text.append(f"Console: {self._console_errors}", style="bold red" if self._console_errors > 0 else "dim")
            text.append("  |  ")
            text.append(f"Warn: {self._console_warnings}", style="bold yellow" if self._console_warnings > 0 else "dim")
            text.append("  |  ")
            text.append(f"404: {self._http_404}", style="bold yellow" if self._http_404 > 0 else "dim")
            text.append("  |  ")
            text.append(f"4xx: {self._http_4xx}", style="bold yellow" if self._http_4xx > 0 else "dim")
            text.append("  |  ")
            text.append(f"5xx: {self._http_5xx}", style="bold red" if self._http_5xx > 0 else "dim")
            text.append("  |  ")
            text.append(f"Timeout: {self._timeouts}", style="bold yellow" if self._timeouts > 0 else "dim")
            text.append("  |  ")
            text.append(f"Ignored: {self._ignored}", style="dim")

        return text

    def set_sitemap(self, sitemap_url: str, url_count: int) -> None:
        """Setzt Sitemap-Info ohne Scan-Ergebnisse.

        Args:
            sitemap_url: URL der Sitemap.
            url_count: Anzahl der URLs in der Sitemap.
        """
        self._sitemap_url = sitemap_url
        self._total_urls = url_count
        self._scanned = 0
        self._console_errors = 0
        self._console_warnings = 0
        self._http_404 = 0
        self._http_4xx = 0
        self._http_5xx = 0
        self._timeouts = 0
        self._ignored = 0
        self._urls_with_errors = 0
        self.refresh()

    def update_from_results(self, results: list[ScanResult]) -> None:
        """Aktualisiert die Zusammenfassung aus den Scan-Ergebnissen.

        Args:
            results: Liste der aktuellen Scan-Ergebnisse.
        """
        self._scanned = sum(
            1 for r in results
            if r.status in (PageStatus.OK, PageStatus.WARNING, PageStatus.ERROR, PageStatus.TIMEOUT)
        )
        self._console_errors = sum(r.console_error_count for r in results)
        self._console_warnings = sum(r.console_warning_count for r in results)
        self._http_404 = sum(r.http_404_count for r in results)
        self._http_4xx = sum(r.http_4xx_count for r in results)
        self._http_5xx = sum(r.http_5xx_count for r in results)
        self._timeouts = sum(1 for r in results if r.status == PageStatus.TIMEOUT)
        self._ignored = sum(r.ignored_count for r in results)
        self._urls_with_errors = sum(1 for r in results if r.has_errors)
        self.refresh()
