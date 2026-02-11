"""Report-Service - Erzeugt HTML- und JSON-Reports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models.scan_result import ScanResult, ScanSummary


class Reporter:
    """Erzeugt Reports aus Scan-Ergebnissen."""

    @staticmethod
    def save_json(
        results: list[ScanResult],
        summary: ScanSummary,
        output_path: str,
    ) -> str:
        """Speichert die Ergebnisse als JSON-Report.

        Args:
            results: Liste der Scan-Ergebnisse.
            summary: Gesamtzusammenfassung.
            output_path: Pfad fuer die JSON-Datei.

        Returns:
            Absoluter Pfad der gespeicherten Datei.
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary.to_dict(),
            "results": [r.to_dict() for r in results],
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        return str(path.resolve())

    @staticmethod
    def save_html(
        results: list[ScanResult],
        summary: ScanSummary,
        output_path: str,
    ) -> str:
        """Speichert die Ergebnisse als HTML-Report (self-contained).

        Args:
            results: Liste der Scan-Ergebnisse.
            summary: Gesamtzusammenfassung.
            output_path: Pfad fuer die HTML-Datei.

        Returns:
            Absoluter Pfad der gespeicherten Datei.
        """
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        duration_s = summary.scan_duration_ms / 1000 if summary.scan_duration_ms > 0 else 0

        # Ergebnis-Zeilen aufbauen
        result_rows = []
        for idx, r in enumerate(results, 1):
            status_class = "ok" if not r.has_errors else "error"
            error_details = ""

            if r.errors:
                detail_items = []
                for e in r.errors:
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

            result_rows.append(
                f"<tr class='{status_class}'>"
                f"<td>{idx}</td>"
                f"<td class='status-cell'>{r.status_icon}</td>"
                f"<td><a href='{_html_escape(r.url)}' target='_blank'>{_html_escape(r.url)}</a></td>"
                f"<td>{r.http_status_code}</td>"
                f"<td>{r.load_time_ms}ms</td>"
                f"<td>{r.console_error_count}</td>"
                f"<td>{r.http_404_count}</td>"
                f"<td>{r.http_4xx_count}</td>"
                f"<td>{r.http_5xx_count}</td>"
                f"</tr>"
            )

            if error_details:
                result_rows.append(
                    f"<tr class='detail-row'><td colspan='9'>{error_details}</td></tr>"
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

        .footer {{ margin-top: 20px; color: #484f58; font-size: 0.8rem; text-align: center; }}
    </style>
</head>
<body>
    <h1>Console Error Scanner Report</h1>
    <p class="timestamp">Erstellt: {timestamp} | Sitemap: {_html_escape(summary.sitemap_url)}</p>

    <div class="summary">
        <div class="summary-card">
            <div class="label">URLs gesamt</div>
            <div class="value">{summary.total_urls}</div>
        </div>
        <div class="summary-card">
            <div class="label">Gescannt</div>
            <div class="value ok">{summary.scanned_urls}</div>
        </div>
        <div class="summary-card">
            <div class="label">Mit Fehlern</div>
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
        <div class="summary-card">
            <div class="label">Dauer</div>
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
                <th>Ladezeit</th>
                <th>Console</th>
                <th>404</th>
                <th>4xx</th>
                <th>5xx</th>
            </tr>
        </thead>
        <tbody>
            {''.join(result_rows)}
        </tbody>
    </table>

    <p class="footer">Console Error Scanner v1.0.0 | {timestamp}</p>
</body>
</html>"""

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

        return str(path.resolve())


def _html_escape(text: str) -> str:
    """Escaped HTML-Sonderzeichen.

    Args:
        text: Zu escapender Text.

    Returns:
        HTML-sicherer Text.
    """
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
