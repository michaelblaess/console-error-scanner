"""Report-Service - Erzeugt HTML- und JSON-Reports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .. import __version__
from ..i18n import t
from ..models.scan_result import ScanResult, ScanSummary, format_page_size
from .site_score import compute_site_score


class Reporter:
    """Erzeugt Reports aus Scan-Ergebnissen."""

    @staticmethod
    def save_json(
        results: list[ScanResult],
        summary: ScanSummary,
        output_path: str,
        error_weight: int = 60,
    ) -> str:
        """Speichert die Ergebnisse als JSON-Report.

        Args:
            results: Liste der Scan-Ergebnisse.
            summary: Gesamtzusammenfassung.
            output_path: Pfad fuer die JSON-Datei.
            error_weight:
                Gewicht der Fehlerquote (Prozent) fuer den Site-Score. Rest =
                Gewicht der Seitengroesse. Default 60 wie in den Settings.

        Returns:
            Absoluter Pfad der gespeicherten Datei.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(Reporter.build_json(results, summary, error_weight), encoding="utf-8")

        return str(path.resolve())

    @staticmethod
    def build_json(results: list[ScanResult], summary: ScanSummary, error_weight: int = 60) -> str:
        """Baut den JSON-Report als String (fuer Datei ODER Zwischenablage).

        Args:
            results:
                Die zu exportierenden Scan-Ergebnisse.
            summary:
                Passende Zusammenfassung zu den Ergebnissen.
            error_weight:
                Gewicht der Fehlerquote (Prozent) fuer den Site-Score.

        Returns:
            JSON-String (indentiert, mit echten Umlauten).
        """
        score = compute_site_score(results, error_weight=error_weight)
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary.to_dict(),
            "site_score": score.to_dict(),
            "results": [r.to_dict() for r in results],
        }
        return json.dumps(report, indent=2, ensure_ascii=False)

    @staticmethod
    def build_text(results: list[ScanResult]) -> str:
        """Baut eine lesbare Plaintext-Liste der Ergebnisse fuer die Zwischenablage.

        Pro Seite eine Kopfzeile (Status, URL, HTTP) und darunter die aktiven
        (nicht-whitelisted) Fehler eingerueckt.

        Args:
            results:
                Die zu exportierenden Scan-Ergebnisse.

        Returns:
            Plaintext-String (leer, wenn keine Ergebnisse).
        """
        lines: list[str] = []
        for r in results:
            http = str(r.http_status_code) if r.http_status_code else "-"
            lines.append(f"{r.status_icon} {r.url} (HTTP {http})")
            for detail in Reporter._error_details(r):
                lines.append(f"    {detail}")
        return "\n".join(lines)

    @staticmethod
    def save_html(
        results: list[ScanResult],
        summary: ScanSummary,
        output_path: str,
        error_weight: int = 60,
    ) -> str:
        """Speichert die Ergebnisse als HTML-Report (self-contained).

        Args:
            results: Liste der Scan-Ergebnisse.
            summary: Gesamtzusammenfassung.
            output_path: Pfad fuer die HTML-Datei.
            error_weight:
                Gewicht der Fehlerquote (Prozent) fuer den Site-Score. Rest =
                Gewicht der Seitengroesse. Default 60 wie in den Settings.

        Returns:
            Absoluter Pfad der gespeicherten Datei.
        """
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        duration_s = summary.scan_duration_ms / 1000 if summary.scan_duration_ms > 0 else 0
        # Site-Score (inkl. groesster Seiten/Ressourcen) wie im TUI-Summary.
        score = compute_site_score(results, error_weight=error_weight)
        pages_entries = [(p.url, format_page_size(p.page_size_bytes), p.page_size_bytes) for p in score.biggest_pages]
        res_entries = [(rs.url, format_page_size(rs.size_bytes), rs.size_bytes) for rs in score.biggest_resources]
        top_sections_html = _top_list_html(t("summary.biggest_pages"), pages_entries) + _top_list_html(
            t("summary.big_fish"), res_entries
        )

        # Ergebnis-Zeilen aufbauen
        result_rows = []
        for idx, r in enumerate(results, 1):
            if r.has_errors:
                status_class = "error"
            elif r.has_issues:
                status_class = "warning"
            else:
                status_class = "ok"
            error_details = ""
            ignored_details = ""

            active_errors = [e for e in r.errors if not e.whitelisted]
            ignored_errors = [e for e in r.errors if e.whitelisted]

            if active_errors:
                detail_items = []
                for e in active_errors:
                    type_label = {
                        "console_error": "Console",
                        "http_404": "HTTP 404",
                        "http_4xx": "HTTP 4xx",
                        "http_5xx": "HTTP 5xx",
                    }.get(e.error_type.value, e.error_type.value)

                    source_info = ""
                    if e.source:
                        source_info = f" <span class='source'>({e.source}"
                        if e.line_number:
                            source_info += f":{e.line_number}"
                        source_info += ")</span>"

                    detail_items.append(
                        f"<li><span class='error-type {e.error_type.value}'>{type_label}</span> "
                        f"{_html_escape(e.message)}{source_info}</li>"
                    )

                error_details = f"<ul class='error-list'>{''.join(detail_items)}</ul>"

            if ignored_errors:
                ignored_items = []
                for e in ignored_errors:
                    type_label = {
                        "console_error": "Console",
                        "console_warning": "Warning",
                        "http_404": "HTTP 404",
                        "http_4xx": "HTTP 4xx",
                        "http_5xx": "HTTP 5xx",
                    }.get(e.error_type.value, e.error_type.value)

                    ignored_items.append(
                        f"<li><span class='error-type ignored'>{type_label}</span> {_html_escape(e.message)}</li>"
                    )

                ignored_details = (
                    f"<div class='ignored-section'>"
                    f"<p class='ignored-header'>{t('report.whitelist_hits', count=len(ignored_errors))}</p>"
                    f"<ul class='error-list ignored-list'>{''.join(ignored_items)}</ul>"
                    f"</div>"
                )

            result_rows.append(
                f"<tr class='{status_class}'>"
                f"<td>{idx}</td>"
                f"<td class='status-cell'>{r.status_icon}</td>"
                f"<td><a href='{_html_escape(r.url)}' target='_blank'>{_html_escape(r.url)}</a></td>"
                f"<td>{r.http_status_code}</td>"
                f"<td>{_fmt_ms(r.load_time_ms)}</td>"
                f"<td>{_fmt_ms(r.dom_content_loaded_ms)}</td>"
                f"<td>{r.request_count if r.request_count > 0 else '-'}</td>"
                f"<td>{format_page_size(r.page_size_bytes)}</td>"
                f"<td>{r.console_error_count}</td>"
                f"<td>{r.http_404_count}</td>"
                f"<td>{r.http_4xx_count}</td>"
                f"<td>{r.http_5xx_count}</td>"
                f"<td class='ignored-cell'>{r.ignored_count}</td>"
                f"</tr>"
            )

            if error_details or ignored_details:
                result_rows.append(
                    f"<tr class='detail-row'><td colspan='13'>{error_details}{ignored_details}</td></tr>"
                )

        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Console Error Scanner Report - {timestamp}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }}
        h1 {{ color: #58a6ff; margin-bottom: 10px; font-size: 1.5rem; }}
        .timestamp {{ color: #8b949e; margin-bottom: 20px; }}

        .summary {{ display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 25px; }}
        .summary-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px 20px; min-width: 140px; }}
        .summary-card .label {{ color: #8b949e; font-size: 0.8rem; text-transform: uppercase; }}
        .summary-card .value {{ font-size: 1.8rem; font-weight: bold; margin-top: 5px; }}
        .summary-card .value.ok {{ color: #3fb950; }}
        .summary-card .value.warning {{ color: #d29922; }}
        .summary-card .value.error {{ color: #f85149; }}

        table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 6px; overflow: hidden; }}
        th {{ background: #21262d; color: #8b949e; text-align: left; padding: 10px 12px; font-size: 0.8rem; text-transform: uppercase; }}
        td {{ padding: 8px 12px; border-top: 1px solid #21262d; font-size: 0.9rem; }}
        tr.ok td {{ color: #c9d1d9; }}
        tr.warning td {{ color: #d29922; }}
        tr.error td {{ color: #f85149; }}
        tr.detail-row td {{ background: #1c2128; padding: 5px 12px 10px 40px; }}

        .status-cell {{ font-weight: bold; }}
        a {{ color: #58a6ff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}

        .error-list {{ list-style: none; padding: 0; }}
        .error-list li {{ padding: 3px 0; font-size: 0.85rem; }}
        .error-type {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.75rem; font-weight: bold; margin-right: 5px; }}
        .error-type.console_error {{ background: #f8514926; color: #f85149; }}
        .error-type.http_404 {{ background: #d2992226; color: #d29922; }}
        .error-type.http_4xx {{ background: #d2992226; color: #d29922; }}
        .error-type.http_5xx {{ background: #f8514926; color: #f85149; }}
        .source {{ color: #8b949e; font-size: 0.8rem; }}

        .ignored-card {{ opacity: 0.6; }}
        .summary-card .value.ignored {{ color: #8b949e; }}
        .ignored-cell {{ color: #8b949e; }}
        .ignored-section {{ margin-top: 10px; padding-top: 8px; border-top: 1px solid #21262d; }}
        .ignored-header {{ color: #8b949e; font-size: 0.8rem; font-weight: bold; margin-bottom: 4px; }}
        .ignored-list li {{ opacity: 0.5; }}
        .error-type.ignored {{ background: #8b949e26; color: #8b949e; }}

        .footer {{ margin-top: 20px; color: #484f58; font-size: 0.8rem; text-align: center; }}

        .score-card {{ border-color: #58a6ff; }}
        .summary-card .value .grade {{ font-size: 1rem; color: #8b949e; font-weight: normal; }}

        .top-section {{ margin-top: 25px; }}
        .top-section h2 {{ color: #58a6ff; font-size: 1.1rem; margin-bottom: 10px; }}
        .top-row {{ display: flex; align-items: center; gap: 10px; padding: 3px 0; font-size: 0.85rem; }}
        .top-val {{ flex: 0 0 80px; text-align: right; font-weight: bold; font-variant-numeric: tabular-nums; }}
        .top-bar {{ flex: 0 0 180px; background: #21262d; border-radius: 3px; height: 14px; overflow: hidden; }}
        .top-fill {{ height: 100%; background: #1f6feb; }}
        .top-url {{ flex: 1 1 auto; word-break: break-all; }}
    </style>
</head>
<body>
    <h1>{t("report.title")}</h1>
    <p class="timestamp">{t("report.created", timestamp=timestamp, url=_html_escape(summary.sitemap_url))}</p>

    <div class="summary">
        <div class="summary-card score-card">
            <div class="label">{t("report.site_score")}</div>
            <div class="value {_score_class(score.score)}">{score.score} %<span class="grade"> ({score.grade})</span></div>
        </div>
        <div class="summary-card">
            <div class="label">{t("report.avg_size")}</div>
            <div class="value">{format_page_size(score.avg_page_size_bytes)}</div>
        </div>
        <div class="summary-card">
            <div class="label">{t("report.urls_total")}</div>
            <div class="value">{summary.total_urls}</div>
        </div>
        <div class="summary-card">
            <div class="label">{t("report.scanned")}</div>
            <div class="value ok">{summary.scanned_urls}</div>
        </div>
        <div class="summary-card">
            <div class="label">{t("report.with_errors")}</div>
            <div class="value {"error" if summary.urls_with_errors > 0 else "ok"}">{summary.urls_with_errors}</div>
        </div>
        <div class="summary-card">
            <div class="label">Console Errors</div>
            <div class="value {"error" if summary.total_console_errors > 0 else "ok"}">{summary.total_console_errors}</div>
        </div>
        <div class="summary-card">
            <div class="label">HTTP 404</div>
            <div class="value {"warning" if summary.total_http_404 > 0 else "ok"}">{summary.total_http_404}</div>
        </div>
        <div class="summary-card">
            <div class="label">HTTP 4xx</div>
            <div class="value {"warning" if summary.total_http_4xx > 0 else "ok"}">{summary.total_http_4xx}</div>
        </div>
        <div class="summary-card">
            <div class="label">HTTP 5xx</div>
            <div class="value {"error" if summary.total_http_5xx > 0 else "ok"}">{summary.total_http_5xx}</div>
        </div>
        <div class="summary-card">
            <div class="label">Timeouts</div>
            <div class="value {"warning" if summary.total_timeouts > 0 else "ok"}">{summary.total_timeouts}</div>
        </div>
        <div class="summary-card ignored-card">
            <div class="label">Ignored</div>
            <div class="value ignored">{summary.total_ignored}</div>
        </div>
        <div class="summary-card">
            <div class="label">{t("report.duration")}</div>
            <div class="value">{duration_s:.1f}s</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Status</th>
                <th>URL</th>
                <th>HTTP</th>
                <th>{t("report.load_time")}</th>
                <th>{t("report.dom_content_loaded")}</th>
                <th>{t("report.requests")}</th>
                <th>{t("table.col_size")}</th>
                <th>Console</th>
                <th>404</th>
                <th>4xx</th>
                <th>5xx</th>
                <th>Ignored</th>
            </tr>
        </thead>
        <tbody>
            {"".join(result_rows)}
        </tbody>
    </table>

    {top_sections_html}

    <p class="footer">Console Error Scanner v{__version__} | {timestamp}</p>
</body>
</html>"""

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

        return str(path.resolve())

    @staticmethod
    def generate_jira_table(results: list[ScanResult], fmt: str = "markdown") -> str:
        """Erzeugt eine JIRA-Tabelle mit allen Seiten, die aktive Fehler haben.

        Beruecksichtigt nur nicht-whitelisted Fehler/Warnungen (has_issues).
        fmt="markdown" erzeugt eine GitHub-Flavored-Markdown-Tabelle fuer Jira
        Cloud (wird beim Einfuegen automatisch in eine ADF-Tabelle konvertiert -
        das alte Wiki Markup versteht der Cloud-Editor nicht mehr). fmt="wiki"
        erzeugt das klassische Wiki Markup fuer Jira Server/Data Center.

        Args:
            results:
                Alle Scan-Ergebnisse.
            fmt:
                "markdown" (Default, Jira Cloud) oder "wiki" (Server/DC).

        Returns:
            JIRA-Tabellen-String fuer die Zwischenablage (leer, wenn keine
            Seite aktive Fehler hat).
        """
        errors = [r for r in results if r.has_issues]
        if not errors:
            return ""

        if fmt.lower() == "wiki":
            return Reporter._jira_table_wiki(errors)
        return Reporter._jira_table_markdown(errors)

    @staticmethod
    def _jira_table_wiki(errors: list[ScanResult]) -> str:
        """Baut die klassische Wiki-Markup-Tabelle (Jira Server/DC).

        Args:
            errors:
                Seiten mit aktiven Fehlern.

        Returns:
            Wiki-Markup-Tabelle als String.
        """
        lines = [t("jira.header")]
        for r in errors:
            http_code = str(r.http_status_code) if r.http_status_code else "-"
            details = Reporter._error_details(r)
            # Details mit \\ als Zellen-Umbruch (Wiki-Markup) - vorab joinen,
            # damit kein Backslash in der f-String-Expression steht.
            detail_str = " \\\\ ".join(details) if details else "-"
            # URL als klickbaren JIRA-Link formatieren.
            lines.append(
                f"|[{r.url}]|{http_code}|{r.status_icon}|{r.console_error_count}|"
                f"{r.http_404_count}|{r.http_4xx_count}|{r.http_5xx_count}|{detail_str}|"
            )
        return "\n".join(lines)

    @staticmethod
    def _jira_table_markdown(errors: list[ScanResult]) -> str:
        """Baut die GFM-Markdown-Tabelle (Jira Cloud, Paste-Konvertierung).

        Args:
            errors:
                Seiten mit aktiven Fehlern.

        Returns:
            Markdown-Tabelle als String.
        """
        # Spaltentitel aus dem uebersetzten Wiki-Header ableiten (mehrsprachig,
        # ohne zweiten i18n-Key): "||A||B||" -> ["A", "B"].
        titles = [c for c in t("jira.header").split("||") if c]
        lines = [
            f"| {' | '.join(titles)} |",
            f"| {' | '.join('---' for _ in titles)} |",
        ]
        for r in errors:
            http_code = str(r.http_status_code) if r.http_status_code else "-"
            details = [Reporter._md_cell(d) for d in Reporter._error_details(r)]
            cells = [
                Reporter._md_cell(r.url),
                http_code,
                r.status_icon,
                str(r.console_error_count),
                str(r.http_404_count),
                str(r.http_4xx_count),
                str(r.http_5xx_count),
                "<br>".join(details) if details else "-",
            ]
            lines.append(f"| {' | '.join(cells)} |")
        return "\n".join(lines)

    @staticmethod
    def _error_details(result: ScanResult) -> list[str]:
        """Liefert die aktiven (nicht-whitelisted) Fehler einer Seite als Texte.

        Args:
            result:
                Das Scan-Ergebnis einer Seite.

        Returns:
            Liste aus "[TYP] Meldung (Quelle:Zeile)"-Strings.
        """
        labels = {
            "console_error": "Console",
            "console_warning": "Warning",
            "http_404": "HTTP 404",
            "http_4xx": "HTTP 4xx",
            "http_5xx": "HTTP 5xx",
        }
        details = []
        for e in result.errors:
            if e.whitelisted:
                continue
            tag = labels.get(e.error_type.value, e.error_type.value)
            source = ""
            if e.source:
                source = f" ({e.source}{f':{e.line_number}' if e.line_number else ''})"
            details.append(f"[{tag}] {e.message}{source}")
        return details

    @staticmethod
    def _md_cell(text: str) -> str:
        """Escapt Pipe und Zeilenumbrueche fuer eine Markdown-Tabellenzelle.

        Args:
            text:
                Roher Zelltext.

        Returns:
            Fuer eine GFM-Tabellenzelle sicherer Text.
        """
        return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _score_class(score: int) -> str:
    """CSS-Klasse (ok/warning/error) zum Site-Score - gleiche Schwellen wie TUI.

    Args:
        score:
            Site-Score 0-100.

    Returns:
        "ok" (>=75), "warning" (>=45) oder "error".
    """
    if score >= 75:
        return "ok"
    if score >= 45:
        return "warning"
    return "error"


def _top_list_html(title: str, entries: list[tuple[str, str, int]]) -> str:
    """Baut eine "Top-Liste"-Sektion (Balken + Wert + Link) fuer den Report.

    Args:
        title:
            Ueberschrift der Sektion.
        entries:
            Liste aus (url, wert_label, wert) - der Balken ist relativ zum
            groessten Wert.

    Returns:
        HTML-Fragment oder leerer String, falls keine Eintraege.
    """
    if not entries:
        return ""
    max_val = max((v for _, _, v in entries), default=1) or 1
    rows = []
    for url, value_str, value in entries:
        pct = max(2, round(100 * value / max_val)) if max_val else 0
        rows.append(
            f"<div class='top-row'>"
            f"<span class='top-val'>{_html_escape(value_str)}</span>"
            f"<div class='top-bar'><div class='top-fill' style='width:{pct}%'></div></div>"
            f"<a class='top-url' href='{_html_escape(url)}' target='_blank'>{_html_escape(url)}</a>"
            f"</div>"
        )
    return f"<section class='top-section'><h2>{_html_escape(title)}</h2>{''.join(rows)}</section>"


def _fmt_ms(ms: int) -> str:
    """Formatiert eine Millisekunden-Zeit fuer den Report.

    Args:
        ms:
            Zeit in Millisekunden (0 = nicht erfasst).

    Returns:
        z.B. "1500ms" oder "-" bei 0.
    """
    return f"{ms}ms" if ms > 0 else "-"


def _html_escape(text: str) -> str:
    """Escaped HTML-Sonderzeichen.

    Args:
        text: Zu escapender Text.

    Returns:
        HTML-sicherer Text.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
