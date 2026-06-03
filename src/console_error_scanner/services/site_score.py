"""Site-Score: bewertet das Gesamtergebnis eines Scans.

Der Score (0-100) setzt sich aus zwei Komponenten zusammen:
- Fehler-Score: Anteil der Seiten OHNE echte Fehler (404/4xx/5xx/Console-Error).
- Groessen-Score: aus der durchschnittlichen Seitengroesse (kleiner = besser).

Die Gewichtung beider Komponenten ist konfigurierbar
(``score_error_weight`` in den Settings).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.scan_result import PageStatus, ResourceSize, ScanResult

# Groessen-Score-Schwellen: bis zu dieser Ø-Groesse volle 100 %, ab der oberen
# Schwelle 0 %, dazwischen linear.
_SIZE_GOOD_BYTES = 2 * 1024 * 1024  # <= 2 MB -> 100 %
_SIZE_BAD_BYTES = 20 * 1024 * 1024  # >= 20 MB -> 0 %


@dataclass
class SiteScore:
    """Aggregiertes Bewertungsergebnis eines kompletten Scans."""

    score: int = 0  # Gesamt 0-100
    error_score: int = 0  # 0-100
    size_score: int = 0  # 0-100
    error_weight: int = 60  # Gewicht Fehler in Prozent (Groesse = Rest)
    total_pages: int = 0  # gescannte Seiten
    clean_pages: int = 0  # Seiten ohne echte Fehler
    pages_with_errors: int = 0
    total_errors: int = 0  # Summe echter Fehler ueber alle Seiten
    total_warnings: int = 0
    avg_page_size_bytes: int = 0
    biggest_pages: list[ScanResult] = field(default_factory=list)
    biggest_resources: list[ResourceSize] = field(default_factory=list)

    @property
    def grade(self) -> str:
        """Schulnoten-aehnliches Kuerzel (A-F) zum Score."""
        s = self.score
        if s >= 90:
            return "A"
        if s >= 75:
            return "B"
        if s >= 60:
            return "C"
        if s >= 45:
            return "D"
        if s >= 30:
            return "E"
        return "F"


def _size_score(avg_bytes: int) -> int:
    """Rechnet die Ø-Seitengroesse in einen 0-100-Score um (kleiner = besser)."""
    if avg_bytes <= _SIZE_GOOD_BYTES:
        return 100
    if avg_bytes >= _SIZE_BAD_BYTES:
        return 0
    span = _SIZE_BAD_BYTES - _SIZE_GOOD_BYTES
    return int(round(100 * (_SIZE_BAD_BYTES - avg_bytes) / span))


def compute_site_score(results: list[ScanResult], error_weight: int = 60) -> SiteScore:
    """Berechnet den Site-Score aus allen gescannten Ergebnissen.

    Args:
        results:
            Alle ScanResults (auch ungescannte werden uebergeben, aber
            herausgefiltert).
        error_weight:
            Gewicht der Fehlerquote in Prozent (0-100). Das Gewicht der
            Seitengroesse ist der Rest (100 - error_weight).

    Returns:
        Ein ``SiteScore`` mit Gesamtscore und Detailwerten.
    """
    weight = max(0, min(100, error_weight))
    scanned = [r for r in results if r.status not in (PageStatus.PENDING, PageStatus.SCANNING)]
    if not scanned:
        return SiteScore(error_weight=weight)

    total = len(scanned)
    clean = sum(1 for r in scanned if not r.has_errors)
    total_errors = sum(
        r.console_error_count + r.http_404_count + r.http_4xx_count + r.http_5xx_count for r in scanned
    )
    total_warnings = sum(r.console_warning_count for r in scanned)
    avg_size = int(sum(r.page_size_bytes for r in scanned) / total)

    error_score = int(round(100 * clean / total))
    size_score = _size_score(avg_size)
    overall = int(round(weight / 100 * error_score + (100 - weight) / 100 * size_score))

    biggest_pages = sorted(scanned, key=lambda r: r.page_size_bytes, reverse=True)[:5]

    # Big Fische: groesste Einzelressourcen ueber alle Seiten, pro URL einmal.
    res_max: dict[str, ResourceSize] = {}
    for r in scanned:
        for res in r.resource_sizes:
            existing = res_max.get(res.url)
            if existing is None or res.size_bytes > existing.size_bytes:
                res_max[res.url] = res
    biggest_resources = sorted(res_max.values(), key=lambda x: x.size_bytes, reverse=True)[:10]

    return SiteScore(
        score=overall,
        error_score=error_score,
        size_score=size_score,
        error_weight=weight,
        total_pages=total,
        clean_pages=clean,
        pages_with_errors=total - clean,
        total_errors=total_errors,
        total_warnings=total_warnings,
        avg_page_size_bytes=avg_size,
        biggest_pages=biggest_pages,
        biggest_resources=biggest_resources,
    )
