"""Datenmodelle fuer Scan-Ergebnisse."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ErrorType(Enum):
    """Art des Fehlers."""

    CONSOLE_ERROR = "console_error"
    CONSOLE_WARNING = "console_warning"
    HTTP_404 = "http_404"
    HTTP_4XX = "http_4xx"
    HTTP_5XX = "http_5xx"


class PageStatus(Enum):
    """Status einer gescannten Seite."""

    PENDING = "pending"
    SCANNING = "scanning"
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class PageError:
    """Ein einzelner Fehler auf einer Seite."""

    error_type: ErrorType
    message: str
    source: str = ""
    line_number: int = 0

    def to_dict(self) -> dict:
        """Konvertiert den Fehler in ein Dictionary."""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "source": self.source,
            "line_number": self.line_number,
        }


@dataclass
class ScanResult:
    """Ergebnis des Scans einer einzelnen Seite."""

    url: str
    status: PageStatus = PageStatus.PENDING
    http_status_code: int = 0
    load_time_ms: int = 0
    errors: list[PageError] = field(default_factory=list)
    retry_count: int = 0

    @property
    def console_error_count(self) -> int:
        """Anzahl der Console-Errors."""
        return sum(1 for e in self.errors if e.error_type == ErrorType.CONSOLE_ERROR)

    @property
    def console_warning_count(self) -> int:
        """Anzahl der Console-Warnings."""
        return sum(1 for e in self.errors if e.error_type == ErrorType.CONSOLE_WARNING)

    @property
    def http_404_count(self) -> int:
        """Anzahl der HTTP 404 Fehler."""
        return sum(1 for e in self.errors if e.error_type == ErrorType.HTTP_404)

    @property
    def http_4xx_count(self) -> int:
        """Anzahl der HTTP 4xx Fehler (ohne 404)."""
        return sum(1 for e in self.errors if e.error_type == ErrorType.HTTP_4XX)

    @property
    def http_5xx_count(self) -> int:
        """Anzahl der HTTP 5xx Fehler."""
        return sum(1 for e in self.errors if e.error_type == ErrorType.HTTP_5XX)

    @property
    def has_errors(self) -> bool:
        """Hat die Seite Fehler?"""
        return len(self.errors) > 0

    @property
    def status_icon(self) -> str:
        """Icon fuer den aktuellen Status."""
        icons = {
            PageStatus.PENDING: "...",
            PageStatus.SCANNING: ">>>",
            PageStatus.OK: "OK",
            PageStatus.ERROR: "ERR",
            PageStatus.TIMEOUT: "T/O",
        }
        return icons.get(self.status, "?")

    @property
    def total_error_count(self) -> int:
        """Gesamtanzahl aller Fehler."""
        return len(self.errors)

    def to_dict(self) -> dict:
        """Konvertiert das Ergebnis in ein Dictionary."""
        return {
            "url": self.url,
            "status": self.status.value,
            "http_status_code": self.http_status_code,
            "load_time_ms": self.load_time_ms,
            "total_errors": self.total_error_count,
            "console_errors": self.console_error_count,
            "console_warnings": self.console_warning_count,
            "http_404_errors": self.http_404_count,
            "http_4xx_errors": self.http_4xx_count,
            "http_5xx_errors": self.http_5xx_count,
            "retry_count": self.retry_count,
            "errors": [e.to_dict() for e in self.errors],
        }


@dataclass
class ScanSummary:
    """Gesamtzusammenfassung eines Scans."""

    sitemap_url: str = ""
    total_urls: int = 0
    scanned_urls: int = 0
    urls_with_errors: int = 0
    total_console_errors: int = 0
    total_console_warnings: int = 0
    total_http_404: int = 0
    total_http_4xx: int = 0
    total_http_5xx: int = 0
    total_timeouts: int = 0
    scan_duration_ms: int = 0

    @staticmethod
    def from_results(sitemap_url: str, results: list[ScanResult], duration_ms: int = 0) -> ScanSummary:
        """Erstellt eine Zusammenfassung aus den Scan-Ergebnissen."""
        summary = ScanSummary(sitemap_url=sitemap_url)
        summary.total_urls = len(results)
        summary.scan_duration_ms = duration_ms

        for result in results:
            if result.status in (PageStatus.OK, PageStatus.ERROR):
                summary.scanned_urls += 1
            if result.has_errors:
                summary.urls_with_errors += 1
            if result.status == PageStatus.TIMEOUT:
                summary.total_timeouts += 1
            summary.total_console_errors += result.console_error_count
            summary.total_console_warnings += result.console_warning_count
            summary.total_http_404 += result.http_404_count
            summary.total_http_4xx += result.http_4xx_count
            summary.total_http_5xx += result.http_5xx_count

        return summary

    def to_dict(self) -> dict:
        """Konvertiert die Zusammenfassung in ein Dictionary."""
        return {
            "sitemap_url": self.sitemap_url,
            "total_urls": self.total_urls,
            "scanned_urls": self.scanned_urls,
            "urls_with_errors": self.urls_with_errors,
            "total_console_errors": self.total_console_errors,
            "total_console_warnings": self.total_console_warnings,
            "total_http_404": self.total_http_404,
            "total_http_4xx": self.total_http_4xx,
            "total_http_5xx": self.total_http_5xx,
            "total_timeouts": self.total_timeouts,
            "scan_duration_ms": self.scan_duration_ms,
        }
