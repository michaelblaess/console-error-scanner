"""Summary-Header als InfoHeader-Subklasse.

Loest das bisherige eigene SummaryPanel(Widget) ab. Die Anzeige folgt dem
Sitemap-Tracker-Pattern: vier Spalten thematisch gruppiert
(Ziel / Konfiguration / Fehler / Fortschritt), collapsible, alle Werte
werden per ``set_value`` aktualisiert.
"""

from __future__ import annotations

from textual_widgets import InfoHeader, InfoItem

from ..i18n import t
from ..models.scan_result import PageStatus, ScanResult


class SummaryHeader(InfoHeader):  # type: ignore[misc]
    """Kopf-Panel mit allen Scan-Informationen in einem 4-Spalten-Raster."""

    def __init__(
        self,
        id: str | None = None,
        concurrency: int = 8,
        timeout: int = 60,
        console_level: str = "warn",
        accept_consent: bool = True,
        trigger_lazy_load: bool = True,
        whitelist_active: bool = False,
    ) -> None:
        items = [
            # Spalte 1: Ziel
            InfoItem("sitemap", t("header.sitemap"), t("header.value_none"), markup=True),
            InfoItem("urls", t("header.urls"), "0"),
            InfoItem("scanned", t("header.scanned"), "0"),
            InfoItem("duration", t("header.duration"), t("header.value_none")),
            # Spalte 2: Konfiguration
            InfoItem("concurrency", t("header.concurrency"), str(concurrency)),
            InfoItem("timeout", t("header.timeout"), f"{timeout}s"),
            InfoItem("level", t("header.level"), console_level),
            InfoItem(
                "consent",
                t("header.consent"),
                self._on_off_text(accept_consent),
                value_style="green" if accept_consent else "dim",
            ),
            # Spalte 3: Fehler-Kategorien
            InfoItem("with_errors", t("header.with_errors"), "0", value_style="dim"),
            InfoItem("console_err", t("header.console_err"), "0", value_style="dim"),
            InfoItem("console_warn", t("header.console_warn"), "0", value_style="dim"),
            InfoItem("ignored", t("header.ignored"), "0", value_style="dim"),
            # Spalte 4: HTTP / Fortschritt
            InfoItem("http_404", t("header.http_404"), "0", value_style="dim"),
            InfoItem("http_4xx", t("header.http_4xx"), "0", value_style="dim"),
            InfoItem("http_5xx", t("header.http_5xx"), "0", value_style="dim"),
            InfoItem("timeouts", t("header.timeouts"), "0", value_style="dim"),
        ]
        super().__init__(
            items,
            columns=4,
            fill="column",
            title=t("header.title"),
            collapsible=True,
            id=id,
        )
        self._scroll_on = trigger_lazy_load
        self._whitelist_active = whitelist_active

    @staticmethod
    def _on_off_text(flag: bool) -> str:
        return t("header.value_on") if flag else t("header.value_off")

    def set_sitemap(self, sitemap_markup: str, url_count: int) -> None:
        """Setzt Sitemap-Anzeige und URL-Zahl.

        Args:
            sitemap_markup: Markup-Snippet (klickbarer Link).
            url_count: Anzahl URLs in der Sitemap.
        """
        self.set_value("sitemap", sitemap_markup)
        self.set_value("urls", str(url_count))
        self.set_value("scanned", "0")
        self.set_value("duration", t("header.value_none"))
        for key in (
            "with_errors",
            "console_err",
            "console_warn",
            "ignored",
            "http_404",
            "http_4xx",
            "http_5xx",
            "timeouts",
        ):
            self.set_value(key, "0", value_style="dim")

    def update_config(
        self,
        concurrency: int,
        timeout: int,
        console_level: str,
        accept_consent: bool,
        trigger_lazy_load: bool,
    ) -> None:
        """Aktualisiert die Konfigurations-Spalte (z.B. nach Settings-Save)."""
        self.set_value("concurrency", str(concurrency))
        self.set_value("timeout", f"{timeout}s")
        self.set_value("level", console_level)
        self.set_value(
            "consent",
            self._on_off_text(accept_consent),
            value_style="green" if accept_consent else "dim",
        )
        self._scroll_on = trigger_lazy_load

    def update_from_results(self, results: list[ScanResult], duration_text: str | None = None) -> None:
        """Aktualisiert die Fehler- und Fortschrittsspalten aus aktuellen Ergebnissen.

        Args:
            results: Aktuelle Scan-Ergebnisse.
            duration_text: Optional bereits formatierte Dauer (z.B. "12.3s").
        """
        scanned = sum(
            1 for r in results if r.status in (PageStatus.OK, PageStatus.WARNING, PageStatus.ERROR, PageStatus.TIMEOUT)
        )
        total = len(results)
        with_errors = sum(1 for r in results if r.has_errors)
        console_err = sum(r.console_error_count for r in results)
        console_warn = sum(r.console_warning_count for r in results)
        http_404 = sum(r.http_404_count for r in results)
        http_4xx = sum(r.http_4xx_count for r in results)
        http_5xx = sum(r.http_5xx_count for r in results)
        timeouts = sum(1 for r in results if r.status == PageStatus.TIMEOUT)
        ignored = sum(r.ignored_count for r in results)

        self.set_value("scanned", f"{scanned}/{total}" if total else "0")
        if duration_text is not None:
            self.set_value("duration", duration_text)

        self.set_value("with_errors", str(with_errors), value_style="bold red" if with_errors else "dim")
        self.set_value("console_err", str(console_err), value_style="bold red" if console_err else "dim")
        self.set_value(
            "console_warn",
            str(console_warn),
            value_style="bold yellow" if console_warn else "dim",
        )
        self.set_value("ignored", str(ignored), value_style="dim")
        self.set_value("http_404", str(http_404), value_style="bold yellow" if http_404 else "dim")
        self.set_value("http_4xx", str(http_4xx), value_style="bold yellow" if http_4xx else "dim")
        self.set_value("http_5xx", str(http_5xx), value_style="bold red" if http_5xx else "dim")
        self.set_value("timeouts", str(timeouts), value_style="bold yellow" if timeouts else "dim")
