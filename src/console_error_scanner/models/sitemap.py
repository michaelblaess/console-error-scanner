"""Sitemap-Parser - Laedt und parst XML-Sitemaps mit Auto-Discovery."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx


# Standard-Namespace fuer Sitemaps
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Typische Sitemap-Pfade fuer Auto-Discovery (in Prioritaetsreihenfolge)
_COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap/sitemap.xml",
    "/sitemapindex.xml",
    "/sitemap/index.xml",
]


def is_sitemap_url(url: str) -> bool:
    """Prueft ob eine URL direkt auf eine Sitemap zeigt.

    Args:
        url: Die zu pruefende URL.

    Returns:
        True wenn die URL auf .xml endet (= direkte Sitemap-URL).
    """
    path = urlparse(url).path.lower()
    return path.endswith(".xml")


def is_local_file(path: str) -> bool:
    """Prueft ob der Pfad auf eine lokale Datei zeigt.

    Args:
        path: Der zu pruefende Pfad oder URL.

    Returns:
        True wenn es ein existierender lokaler Dateipfad ist.
    """
    if path.lower().startswith(("http://", "https://")):
        return False
    return Path(path).is_file()


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
        """Laedt die Sitemap per HTTP oder aus lokaler Datei.

        Returns:
            XML-Inhalt der Sitemap als String.

        Raises:
            SitemapError: Wenn die Sitemap nicht geladen werden kann.
        """
        # Lokale Datei direkt lesen
        if is_local_file(self.sitemap_url):
            return self._read_local_file(self.sitemap_url)

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

    @staticmethod
    def _read_local_file(file_path: str) -> str:
        """Liest eine lokale Sitemap-XML-Datei.

        Args:
            file_path: Pfad zur lokalen XML-Datei.

        Returns:
            Datei-Inhalt als String.

        Raises:
            SitemapError: Wenn die Datei nicht gelesen werden kann.
        """
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return Path(file_path).read_text(encoding="latin-1")
            except Exception as e:
                raise SitemapError(f"Datei konnte nicht gelesen werden: {file_path} ({e})")
        except Exception as e:
            raise SitemapError(f"Datei konnte nicht gelesen werden: {file_path} ({e})")

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


async def discover_sitemap(
    base_url: str,
    cookies: list[dict[str, str]] | None = None,
    log: callable = None,
) -> str:
    """Findet die Sitemap-URL fuer eine Domain automatisch.

    Strategie:
    1. robots.txt laden und nach "Sitemap:"-Eintraegen suchen
    2. Typische Pfade durchprobieren (/sitemap.xml, /sitemap/sitemap.xml, ...)
    3. Erste funktionierende URL zurueckgeben

    Args:
        base_url: Basis-URL der Website (z.B. https://www.example.com).
        cookies: Optionale Cookies fuer authentifizierte Zugriffe.
        log: Optionale Log-Funktion fuer Statusmeldungen.

    Returns:
        Die gefundene Sitemap-URL.

    Raises:
        SitemapError: Wenn keine Sitemap gefunden wird.
    """
    if log is None:
        log = lambda msg: None

    # Basis-URL normalisieren (Trailing Slash entfernen)
    parsed = urlparse(base_url)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

    # Cookies aufbereiten
    jar = httpx.Cookies()
    for c in (cookies or []):
        jar.set(c["name"], c["value"])

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        verify=False,
        cookies=jar,
    ) as client:

        # Phase 1: robots.txt nach Sitemap-Eintraegen durchsuchen
        robots_url = f"{origin}/robots.txt"
        log(f"    Suche Sitemap in robots.txt: {robots_url}")
        try:
            response = await client.get(robots_url)
            if response.status_code == 200:
                sitemap_urls = _parse_robots_sitemaps(response.text)
                for sitemap_url in sitemap_urls:
                    log(f"    robots.txt Eintrag gefunden: {sitemap_url}")
                    if await _is_valid_sitemap(client, sitemap_url):
                        log(f"    [green]Sitemap gefunden: {sitemap_url}[/green]")
                        return sitemap_url
                    log(f"    {sitemap_url} nicht erreichbar, weiter...")
        except Exception:
            log("    robots.txt nicht erreichbar")

        # Phase 2: Typische Pfade durchprobieren
        log("    Probiere typische Sitemap-Pfade...")
        for path in _COMMON_SITEMAP_PATHS:
            candidate = f"{origin}{path}"
            log(f"    Teste: {candidate}")
            if await _is_valid_sitemap(client, candidate):
                log(f"    [green]Sitemap gefunden: {candidate}[/green]")
                return candidate

    raise SitemapError(
        f"Keine Sitemap gefunden fuer {base_url}\n\n"
        f"Getestet: robots.txt + {len(_COMMON_SITEMAP_PATHS)} typische Pfade.\n"
        f"Bitte gib die Sitemap-URL direkt an, z.B.:\n"
        f"  {origin}/pfad/zur/sitemap.xml"
    )


def _parse_robots_sitemaps(robots_text: str) -> list[str]:
    """Extrahiert Sitemap-URLs aus robots.txt.

    Args:
        robots_text: Inhalt der robots.txt.

    Returns:
        Liste der gefundenen Sitemap-URLs.
    """
    urls: list[str] = []
    for line in robots_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            url = stripped[len("sitemap:"):].strip()
            if url:
                urls.append(url)
    return urls


async def _is_valid_sitemap(client: httpx.AsyncClient, url: str) -> bool:
    """Prueft ob eine URL eine gueltige Sitemap zurueckliefert.

    Args:
        client: httpx Client-Instanz.
        url: Die zu pruefende URL.

    Returns:
        True wenn die URL HTTP 200 liefert und XML-Inhalt enthaelt.
    """
    try:
        response = await client.head(url)
        if response.status_code == 200:
            # HEAD war erfolgreich - kurz pruefen ob XML-Content
            content_type = response.headers.get("content-type", "")
            if "xml" in content_type or "text" in content_type:
                return True
            # Manche Server liefern keinen korrekten Content-Type bei HEAD,
            # deshalb GET als Fallback mit wenig Daten
            response = await client.get(url, headers={"Range": "bytes=0-512"})
            if response.status_code in (200, 206):
                text = response.text[:512]
                return "<?xml" in text or "<urlset" in text or "<sitemapindex" in text
    except Exception:
        pass
    return False


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
