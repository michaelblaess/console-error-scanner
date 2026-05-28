"""Statistik-/Detail-Panel - thematische Rich-Panels fuer die markierte URL.

Loest die alte ErrorDetailView ab. Aufbau analog sitemap-tracker:
- Page-Panel: URL, Status, HTTP, Ladezeit, Groesse, Content-Type, …
- HTTP-Headers-Panel (sofern vorhanden)
- Errors-Panel (rot): HTTP 4xx + 5xx + Console-Errors
- Warnings-Panel (gelb): Console-Warnings + CSP-Violations + HTTP 404
- Whitelist-Panel (dim): unterdrueckte Eintraege
- Info-Panel (cyan): Statusmeldungen (Scan laeuft, keine Fehler, nicht gescannt)
"""

from __future__ import annotations

import contextlib
import re
from urllib.parse import quote, urlparse, urlunparse

from rich.console import Group
from rich.markup import escape as escape_markup
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from ..i18n import t
from ..models.scan_result import ErrorType, PageStatus, ScanResult, format_page_size


def _sanitize_url(url: str) -> str:
    """Bereinigt eine URL fuer Terminal-Klick-Kompatibilitaet."""
    parsed = urlparse(url)
    safe_path = quote(parsed.path, safe="/:@!$&'*+,;=-._~%")
    safe_query = quote(parsed.query, safe="/:@!$&'*+,;=-._~?=%")
    return urlunparse((parsed.scheme, parsed.netloc, safe_path, parsed.params, safe_query, parsed.fragment))


def _format_load_time(ms: float) -> str:
    """Formatiert eine Ladezeit (de-DE-Komma)."""
    if ms <= 0:
        return "-"
    if ms >= 1000:
        return f"{ms / 1000:.1f}".replace(".", ",") + "s"
    return f"{ms:.0f}ms"


# Stack-Trace-URL-Kuerzung (übernommen aus altem ErrorDetailView)
_URL_PATTERN = re.compile(r"https?://[^\s\)]+")
_MAX_PATH_DISPLAY_LEN = 60


def _shorten_stack_line(line: str) -> str:
    """Kuerzt URLs in einer Stack-Trace-Zeile."""
    line = line.strip()
    if not line:
        return line
    shortened = _URL_PATTERN.sub(lambda m: _shorten_url(m.group(0)), line)
    if len(shortened) > 90:
        shortened = f"{shortened[:87]}..."
    return shortened


def _shorten_url(url: str) -> str:
    if len(url) <= _MAX_PATH_DISPLAY_LEN:
        return url
    clean = url.split("?")[0].split("#")[0]
    path_start = clean.find("//")
    if path_start >= 0:
        after_protocol = clean[path_start + 2 :]
        slash_pos = after_protocol.find("/")
        path = after_protocol[slash_pos:] if slash_pos >= 0 else ""
    else:
        path = clean
    segments = [s for s in path.split("/") if s]
    if len(segments) <= 2:
        return url[: _MAX_PATH_DISPLAY_LEN - 3] + "..."
    last = segments[-1]
    short = f".../{segments[-2]}/{last}"
    if len(short) > _MAX_PATH_DISPLAY_LEN:
        short = f".../{last}"
    return short


class StatsPanel(VerticalScroll):
    """Detail-Panel der markierten URL — analog sitemap-tracker.StatsPanel."""

    # Schwellwert: ab so vielen HTTP-Headern wird das Panel default collapsed.
    _HEADERS_COLLAPSE_THRESHOLD = 5

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result: ScanResult | None = None
        # Pro-URL gemerkter Aufgeklappt-Zustand fuer das HTTP-Header-Panel,
        # damit der User-Toggle nicht beim naechsten Highlight zurueckspringt.
        self._headers_expanded: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        yield Static(self._placeholder_markup(), id="stats-content", markup=True)

    # --- Helper -------------------------------------------------------------

    def _link(self, text: str, target: str) -> str:
        link_fn = getattr(self.app, "link_markup", None)
        if callable(link_fn):
            return link_fn(escape_markup(text), target)
        return escape_markup(text)

    def _detail_value(self, value: str, value_style: str = "", link_url: str = "") -> Text:
        """Wert-Renderable einer Detail-Zeile mit fold-Umbruch und Hover-Link."""
        if link_url:
            link_fn = getattr(self.app, "link_markup", None)
            if callable(link_fn):
                sub = Text.from_markup(link_fn(value, link_url), overflow="fold")
                if value_style:
                    sub.stylize(value_style)
                return sub
            style = f"{value_style} link {link_url}".strip()
            return Text(value, style=style, overflow="fold")
        if value_style:
            return Text(value, style=value_style, overflow="fold")
        return Text(value, overflow="fold")

    @staticmethod
    def _kv_table(rows: list[tuple[str, Text]]) -> Table:
        """2-spaltiges Grid (Label | Wert) mit Hanging-Indent."""
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(no_wrap=True, style="dim", justify="left")
        grid.add_column(ratio=1, overflow="fold")
        for label, value in rows:
            grid.add_row(label, value)
        return grid

    @staticmethod
    def _panel(title: str, body: list, border_style: str = "grey37") -> Panel:
        """Bordiertes Panel mit linksbuendigem Titel."""
        return Panel(
            Group(*body) if body else Text(""),
            title=f" {title} ",
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
        )

    # --- Panels -------------------------------------------------------------

    def _placeholder_markup(self) -> str:
        return f"[dim italic]{escape_markup(t('detail.no_url'))}[/]"

    def _page_panel(self, result: ScanResult) -> Panel:
        safe_url = _sanitize_url(result.url)
        rows: list[tuple[str, Text]] = [
            (t("detail.url"), self._detail_value(safe_url, "bold", link_url=safe_url)),
            (t("detail.status"), self._detail_value(f"{result.status_icon} {result.status.value}")),
            (t("detail.http"), self._detail_value(str(result.http_status_code) if result.http_status_code else "-")),
            (t("detail.load_time"), self._detail_value(_format_load_time(result.load_time_ms))),
            (t("detail.size"), self._detail_value(format_page_size(result.page_size_bytes))),
        ]
        if result.retry_count > 0:
            rows.append((t("detail.retries_label"), self._detail_value(str(result.retry_count), "yellow")))
        if result.content_type:
            rows.append((t("detail.content_type"), self._detail_value(result.content_type)))
        if result.last_modified:
            rows.append((t("detail.last_modified"), self._detail_value(result.last_modified)))
        return self._panel(t("detail.page_heading"), [self._kv_table(rows)])

    def _http_headers_panel(self, result: ScanResult) -> Panel | None:
        """HTTP-Header-Panel — bei mehr als N Headern default collapsed mit
        klickbarem ▶/▼-Indikator im Titel.

        Default-Zustand: collapsed wenn > _HEADERS_COLLAPSE_THRESHOLD, sonst
        expanded. Der User-Toggle wird pro URL in ``self._headers_expanded``
        gemerkt, damit das Panel nicht beim naechsten Highlight zuruekspringt.
        """
        if not result.response_headers:
            return None
        count = len(result.response_headers)
        # Default: kleine Listen sind immer offen, große Listen default zu.
        default_expanded = count <= self._HEADERS_COLLAPSE_THRESHOLD
        expanded = self._headers_expanded.get(result.url, default_expanded)

        arrow = "▼" if expanded else "▶"
        # Klickbarer Titel via Textual-Action-Markup im Panel-Titel.
        # Markup-fähiger Text - Rich-Panel akzeptiert Text als Titel.
        title_text = Text.from_markup(
            f"[@click=app.toggle_stats_headers] {arrow} {escape_markup(t('detail.http_heading'))} ({count}) [/]"
        )
        if expanded:
            body: list = [self._kv_table([(n, self._detail_value(v)) for n, v in result.response_headers.items()])]
        else:
            body = [Text(t("detail.http_collapsed_hint", count=count), style="dim italic")]
        return Panel(
            Group(*body),
            title=title_text,
            title_align="left",
            border_style="grey37",
            padding=(0, 1),
        )

    def toggle_headers(self) -> None:
        """Toggle Collapse-Zustand des HTTP-Header-Panels fuer die aktuelle URL."""
        if self._result is None:
            return
        count = len(self._result.response_headers)
        default_expanded = count <= self._HEADERS_COLLAPSE_THRESHOLD
        current = self._headers_expanded.get(self._result.url, default_expanded)
        self._headers_expanded[self._result.url] = not current
        self.refresh_view()

    def _errors_panel(self, result: ScanResult) -> Panel | None:
        """HTTP 4xx + 5xx + Console-Errors (alle nicht-whitelisted)."""
        types = {ErrorType.HTTP_404, ErrorType.HTTP_4XX, ErrorType.HTTP_5XX, ErrorType.CONSOLE_ERROR}
        errors = [e for e in result.errors if e.error_type in types and not e.whitelisted]
        if not errors:
            return None
        body: list = []
        for idx, error in enumerate(errors, 1):
            body.append(self._render_error_entry(idx, error, accent="bold red"))
            if idx < len(errors):
                body.append(Text("─" * 60, style="dim"))
        return self._panel(t("detail.errors_heading", count=len(errors)), body, border_style="red")

    def _warnings_panel(self, result: ScanResult) -> Panel | None:
        """Console-Warnings (incl. CSP-Violations)."""
        warns = [e for e in result.errors if e.error_type == ErrorType.CONSOLE_WARNING and not e.whitelisted]
        if not warns:
            return None
        body: list = []
        for idx, error in enumerate(warns, 1):
            body.append(self._render_error_entry(idx, error, accent="bold yellow"))
            if idx < len(warns):
                body.append(Text("─" * 60, style="dim"))
        return self._panel(t("detail.warnings_heading", count=len(warns)), body, border_style="yellow")

    def _whitelist_panel(self, result: ScanResult) -> Panel | None:
        """Whitelist-ignorierte Eintraege (dim)."""
        ignored = [e for e in result.errors if e.whitelisted]
        if not ignored:
            return None
        type_labels = {
            ErrorType.CONSOLE_ERROR: "Console",
            ErrorType.CONSOLE_WARNING: "Warning",
            ErrorType.HTTP_404: "HTTP 404",
            ErrorType.HTTP_4XX: "HTTP 4xx",
            ErrorType.HTTP_5XX: "HTTP 5xx",
        }
        body: list = []
        for idx, error in enumerate(ignored, 1):
            label = type_labels.get(error.error_type, error.error_type.value)
            msg = error.message
            if len(msg) > 100:
                msg = msg[:97] + "..."
            line = Text(overflow="fold")
            line.append(f"  {idx}. ", style="dim")
            line.append(f"[{label}] ", style="dim cyan")
            line.append(msg, style="dim")
            body.append(line)
        return self._panel(t("detail.whitelist_heading", count=len(ignored)), body, border_style="grey37")

    def _info_panel(self, result: ScanResult) -> Panel | None:
        """Info-Panel: Statusmeldungen wenn keine Fehler / nicht gescannt."""
        msg: str
        style: str
        if result.status == PageStatus.SCANNING:
            msg, style = t("detail.scanning"), "cyan"
        elif result.status == PageStatus.PENDING:
            msg, style = t("detail.not_scanned"), "dim"
        elif result.status == PageStatus.OK and not result.errors:
            msg, style = t("detail.no_errors"), "green"
        elif result.status == PageStatus.TIMEOUT:
            msg, style = t("detail.timeout"), "yellow"
        else:
            return None
        body = [Text(msg, style=style)]
        return self._panel(t("detail.info_heading"), body, border_style="cyan")

    def _render_error_entry(self, idx: int, error, accent: str) -> Text:
        """Rendert einen Error/Warning-Eintrag mit Message + Stack + Quelle."""
        msg_lines = error.message.split("\n") if error.message else [t("detail.no_text")]
        first_line = msg_lines[0]
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."

        line = Text(overflow="fold")
        line.append(f"  {idx}. ", style=accent)
        line.append(first_line, style="bold white")

        # Stack-Trace (max 3 weitere Zeilen)
        for extra in msg_lines[1:4]:
            short = _shorten_stack_line(extra)
            line.append("\n       ")
            line.append(short, style="dim")
        if len(msg_lines) > 4:
            line.append("\n       ")
            line.append(t("detail.more_lines", count=len(msg_lines) - 4), style="dim")

        # Quelle als Hover-Link
        if error.source:
            source = error.source
            if error.line_number:
                source = f"{source}:{error.line_number}"
            line.append("\n       ")
            line.append(t("detail.source").strip())
            line.append(" ")
            link_fn = getattr(self.app, "link_markup", None)
            if callable(link_fn):
                link_text = Text.from_markup(link_fn(source, error.source))
                link_text.stylize("dim cyan")
                line.append_text(link_text)
            else:
                line.append(source, style=f"dim cyan link {error.source}")
        return line

    # --- Public API ---------------------------------------------------------

    def show_result(self, result: ScanResult) -> None:
        """Zeigt Detail-Infos zur markierten URL."""
        self._result = result
        panels: list = [self._page_panel(result)]

        headers_panel = self._http_headers_panel(result)
        if headers_panel is not None:
            panels.append(headers_panel)

        errors_panel = self._errors_panel(result)
        if errors_panel is not None:
            panels.append(errors_panel)

        warnings_panel = self._warnings_panel(result)
        if warnings_panel is not None:
            panels.append(warnings_panel)

        whitelist_panel = self._whitelist_panel(result)
        if whitelist_panel is not None:
            panels.append(whitelist_panel)

        info_panel = self._info_panel(result)
        if info_panel is not None:
            panels.append(info_panel)

        content = self.query_one("#stats-content", Static)
        content.update(Group(*panels))

    def clear(self) -> None:
        """Setzt das Panel zurueck."""
        self._result = None
        with contextlib.suppress(Exception):
            self.query_one("#stats-content", Static).update(self._placeholder_markup())

    def selected_result(self) -> ScanResult | None:
        """Gibt das aktuell angezeigte Result zurueck (fuer copy_details)."""
        return self._result

    def refresh_view(self) -> None:
        """Erneut zeichnen (z.B. nach Whitelist-Aenderung)."""
        if self._result is not None:
            self.show_result(self._result)
