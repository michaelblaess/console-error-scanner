"""Sitemap-Parser - Laedt und parst XML-Sitemaps."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx


# Standard-Namespace fuer Sitemaps
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


class SitemapParser:
    """Laedt eine Sitemap per HTTP und extrahiert URLs."""

    def __init__(
        self,
        sitemap_url: str,
        url_filter: str = "",
        cookies: list[dict[str, str]] | None = None,
    ) -> None:
        self.sitemap_url = sitemap_url
        self.url_filter = url_filter
        self.cookies = cookies or []

    async def parse(self) -> list[str]:
        """Laedt die Sitemap und gibt die enthaltenen URLs zurueck.

        Returns:
            Liste der URLs aus der Sitemap.

        Raises:
            SitemapError: Wenn die Sitemap nicht geladen oder geparst werden kann.
        """
        xml_content = await self._fetch_sitemap()
        urls = self._parse_xml(xml_content)

        if self.url_filter:
            filter_lower = self.url_filter.lower()
            urls = [u for u in urls if filter_lower in u.lower()]

        return urls

    async def _fetch_sitemap(self) -> str:
        """Laedt die Sitemap per HTTP mit Retry-Logik.

        Returns:
            XML-Inhalt der Sitemap als String.

        Raises:
            SitemapError: Wenn die Sitemap nach 3 Versuchen nicht geladen werden kann.
        """
        max_retries = 3
        last_error = None

        # Cookies fuer httpx aufbereiten: {"name": "x", "value": "y"} -> httpx.Cookies
        jar = httpx.Cookies()
        for c in self.cookies:
            jar.set(c["name"], c["value"])

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=True,
                    verify=False,
                    cookies=jar,
                ) as client:
                    response = await client.get(self.sitemap_url)
                    response.raise_for_status()
                    return response.text
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    import asyncio
                    wait_time = 5 * (2 ** attempt)
                    await asyncio.sleep(wait_time)

        raise SitemapError(f"Sitemap konnte nach {max_retries} Versuchen nicht geladen werden: {last_error}")

    def _parse_xml(self, xml_content: str) -> list[str]:
        """Parst den XML-Inhalt und extrahiert URLs.

        Args:
            xml_content: XML-String der Sitemap.

        Returns:
            Liste der gefundenen URLs.

        Raises:
            SitemapError: Wenn das XML nicht geparst werden kann.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise SitemapError(f"Sitemap-XML konnte nicht geparst werden: {e}")

        urls: list[str] = []

        # Sitemapindex: enthaelt <sitemap><loc>...</loc></sitemap>
        sitemap_entries = root.findall(f"{{{SITEMAP_NS}}}sitemap/{{{SITEMAP_NS}}}loc")
        if sitemap_entries:
            # Sitemapindex gefunden - wir geben die Sub-Sitemap-URLs zurueck
            # In einer spaeteren Version koennten wir diese rekursiv laden
            for entry in sitemap_entries:
                if entry.text:
                    urls.append(entry.text.strip())
            return urls

        # Normale Sitemap: enthaelt <url><loc>...</loc></url>
        url_entries = root.findall(f"{{{SITEMAP_NS}}}url/{{{SITEMAP_NS}}}loc")
        for entry in url_entries:
            if entry.text:
                urls.append(_sanitize_url(entry.text.strip()))

        # Fallback ohne Namespace (manche Sitemaps haben keinen)
        if not urls:
            url_entries = root.findall("url/loc")
            for entry in url_entries:
                if entry.text:
                    urls.append(_sanitize_url(entry.text.strip()))

            sitemap_entries = root.findall("sitemap/loc")
            for entry in sitemap_entries:
                if entry.text:
                    urls.append(_sanitize_url(entry.text.strip()))

        return urls


def _sanitize_url(url: str) -> str:
    """Bereinigt eine URL fuer bessere Terminal-Kompatibilitaet.

    Kodiert Klammern als %28/%29, da Terminals diese beim Ctrl+Click
    nicht als Teil der URL erkennen.

    Args:
        url: Die zu bereinigende URL.

    Returns:
        Bereinigte URL.
    """
    return url.replace("(", "%28").replace(")", "%29")


class SitemapError(Exception):
    """Fehler beim Laden oder Parsen einer Sitemap."""
    pass
