"""Tests fuer den JIRA-Tabellen-Export (Markdown fuer Cloud, Wiki fuer Server/DC)."""

from __future__ import annotations

import pytest

from console_error_scanner.i18n import load_locale
from console_error_scanner.models.scan_result import (
    ErrorType,
    PageError,
    PageStatus,
    ScanResult,
)
from console_error_scanner.services.reporter import Reporter


@pytest.fixture(autouse=True)
def _german_locale() -> None:
    load_locale("de")


def _err_page(
    url: str,
    *,
    message: str = "Uncaught ReferenceError: x is not defined",
    source: str = "app.js",
    line_number: int = 42,
    whitelisted: bool = False,
    error_type: ErrorType = ErrorType.CONSOLE_ERROR,
    http_status_code: int = 200,
) -> ScanResult:
    return ScanResult(
        url=url,
        status=PageStatus.ERROR,
        http_status_code=http_status_code,
        errors=[
            PageError(
                error_type=error_type,
                message=message,
                source=source,
                line_number=line_number,
                whitelisted=whitelisted,
            )
        ],
    )


def test_no_issues_returns_empty() -> None:
    ok = ScanResult(url="https://ex.com/a", status=PageStatus.OK, http_status_code=200)
    assert Reporter.generate_jira_table([ok]) == ""


def test_only_whitelisted_is_excluded() -> None:
    page = _err_page("https://ex.com/w", whitelisted=True)
    assert Reporter.generate_jira_table([page]) == ""


def test_markdown_is_default_with_separator_row() -> None:
    out = Reporter.generate_jira_table([_err_page("https://ex.com/tot")]).splitlines()
    # Header aus dem uebersetzten Wiki-Header abgeleitet (8 Spalten) + Trennzeile
    assert out[0].startswith("| URL | HTTP | Status |")
    assert out[1] == "| --- | --- | --- | --- | --- | --- | --- | --- |"
    assert "https://ex.com/tot" in out[2]
    assert "ERR" in out[2]
    # Detail-Zelle enthaelt Typ, Meldung und Quelle
    assert "[Console] Uncaught ReferenceError" in out[2]
    assert "(app.js:42)" in out[2]


def test_markdown_escapes_pipe_in_cells() -> None:
    page = _err_page("https://ex.com/a|b", message="a | b failed")
    row = Reporter.generate_jira_table([page]).splitlines()[2]
    assert "https://ex.com/a\\|b" in row
    assert "a \\| b failed" in row


def test_wiki_format_uses_wiki_header_and_link() -> None:
    out = Reporter.generate_jira_table([_err_page("https://ex.com/tot")], fmt="wiki").splitlines()
    assert out[0].startswith("||URL||HTTP||Status||")
    assert out[1].startswith("|[https://ex.com/tot]|")
    assert "[Console] Uncaught ReferenceError" in out[1]


def test_fmt_is_case_insensitive() -> None:
    page = _err_page("https://ex.com/tot")
    assert Reporter.generate_jira_table([page], fmt="WIKI").startswith("||URL||")
    assert Reporter.generate_jira_table([page], fmt="Markdown").startswith("| URL |")
