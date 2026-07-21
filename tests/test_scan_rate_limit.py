"""Integrationstest: greift das Rate-Limit im echten Scan-Pfad?

Der Unit-Test in test_rate_limit.py prueft nur den Limiter selbst. Hier laeuft
Scanner.scan() vollstaendig durch - lediglich der Browser-Start und die
eigentliche Seitenpruefung sind ersetzt, damit der Test ohne Playwright und
ohne Netzwerk auskommt. Faellt die Verdrahtung im Scanner weg, sind gedrosselter
und ungedrosselter Lauf gleich schnell und der Test schlaegt fehl.
"""

from __future__ import annotations

import asyncio
import time

from console_error_scanner.models.scan_result import ScanResult
from console_error_scanner.services import scanner as scanner_module
from console_error_scanner.services.scanner import Scanner

_PAGE_COUNT = 5


class _FakePlaywright:
    """Ersetzt async_playwright(): liefert ein Objekt mit start()/stop()."""

    async def start(self) -> _FakePlaywright:
        return self

    async def stop(self) -> None:
        return None


def _scan_seconds(rate_per_minute: int, monkeypatch) -> float:  # type: ignore[no-untyped-def]
    """Misst einen kompletten Scan-Durchlauf ohne Browser und ohne Netzwerk."""
    monkeypatch.setattr(scanner_module, "async_playwright", lambda: _FakePlaywright())

    scanner = Scanner(concurrency=8, timeout=5, rate_per_minute=rate_per_minute)

    async def fake_launch() -> object:
        return object()

    async def fake_scan_single(result: ScanResult, log: object) -> None:
        return None

    async def fake_close() -> None:
        return None

    monkeypatch.setattr(scanner, "_launch_browser", fake_launch)
    monkeypatch.setattr(scanner, "_scan_single_page", fake_scan_single)
    monkeypatch.setattr(scanner, "_cleanup", fake_close)

    results = [ScanResult(url=f"https://example.com/seite-{i}") for i in range(_PAGE_COUNT)]

    start = time.monotonic()
    asyncio.run(scanner.scan_urls(results))
    return time.monotonic() - start


class TestScanRateLimit:
    def test_unlimited_scan_is_fast(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Referenzlauf: ohne Limit ist der Durchlauf in Sekundenbruchteilen fertig."""
        assert _scan_seconds(0, monkeypatch) < 1.0

    def test_rate_limit_slows_the_scan_down(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """1200/Minute = 50 ms Abstand; fuenf Seiten warten also mehrere Intervalle."""
        # Untere Schranke mit Abstand zum Sollwert (200 ms): die Timeraufloesung
        # unter Windows liegt bei rund 15 ms, ein exakter Wert waere flaky.
        assert _scan_seconds(1200, monkeypatch) >= 0.15
