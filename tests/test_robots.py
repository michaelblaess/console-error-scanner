"""Tests fuer die robots.txt-Auswertung (nur Seiten, keine Bilder)."""

from __future__ import annotations

import asyncio

import httpx

from console_error_scanner.models.robots import RobotsChecker

_ROBOTS = """
# Kommentar wird ignoriert
User-agent: BadBot
Disallow: /

User-agent: *
Disallow: /intern/
Disallow: /suche
Allow: /intern/presse/
Sitemap: https://example.com/sitemap.xml
"""


def _load(text: str, status: int = 200) -> RobotsChecker:
    """Laedt robots.txt ueber einen MockTransport - wie in test_sitemap_discovery."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=text)

    async def scenario() -> RobotsChecker:
        checker = RobotsChecker()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await checker.load("https://example.com/irgendeine/seite", client=client)
        return checker

    return asyncio.run(scenario())


class TestRobotsChecker:
    def test_disallowed_path_blocked(self) -> None:
        assert _load(_ROBOTS).is_allowed("https://example.com/intern/geheim") is False

    def test_allow_wins_over_shorter_disallow(self) -> None:
        """Laengere (spezifischere) Regel gewinnt - sonst waere die Presse gesperrt."""
        assert _load(_ROBOTS).is_allowed("https://example.com/intern/presse/pm-1") is True

    def test_normal_page_allowed(self) -> None:
        assert _load(_ROBOTS).is_allowed("https://example.com/produkte/strom") is True

    def test_other_agent_block_ignored(self) -> None:
        """Das `Disallow: /` von BadBot darf uns nicht treffen."""
        assert _load(_ROBOTS).is_allowed("https://example.com/") is True

    def test_missing_robots_allows_everything(self) -> None:
        """404 = keine Regeln = alles erlaubt (freundliche Auslegung)."""
        checker = _load("nicht gefunden", status=404)
        assert checker.is_allowed("https://example.com/intern/geheim") is True
        assert checker.is_loaded is True

    def test_network_error_allows_everything(self) -> None:
        """Auch ein Verbindungsfehler darf den Scan nicht blockieren."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("kein Netz")

        async def scenario() -> RobotsChecker:
            checker = RobotsChecker()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await checker.load("https://example.com/seite", client=client)
            return checker

        assert asyncio.run(scenario()).is_allowed("https://example.com/intern/x") is True

    def test_empty_disallow_is_no_rule(self) -> None:
        """`Disallow:` ohne Pfad heisst ausdruecklich: alles erlaubt."""
        checker = _load("User-agent: *\nDisallow:\n")
        assert checker.is_allowed("https://example.com/beliebig") is True

    def test_wildcard_pattern(self) -> None:
        """`*` steht fuer eine beliebige Zeichenfolge (RFC 9309)."""
        checker = _load("User-agent: *\nDisallow: /*/print\n")
        assert checker.is_allowed("https://example.com/news/print") is False
        assert checker.is_allowed("https://example.com/news/artikel") is True

    def test_end_anchor(self) -> None:
        """`$` verankert das Pfadende - echte Regel von spiegel.de."""
        checker = _load("User-agent: *\nDisallow: /*CR-Dokumentation.pdf$\n")
        assert checker.is_allowed("https://example.com/a/CR-Dokumentation.pdf") is False
        assert checker.is_allowed("https://example.com/a/CR-Dokumentation.pdf.html") is True

    def test_allow_wins_on_equal_length(self) -> None:
        """Bei gleich langen Regeln gewinnt Allow (RFC 9309)."""
        checker = _load("User-agent: *\nDisallow: /abc\nAllow: /abc\n")
        assert checker.is_allowed("https://example.com/abc") is True
