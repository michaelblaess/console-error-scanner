"""Seiten-Vorschau: Screenshots per Playwright-Sidecar.

Eigenstaendige Playwright-Instanz nur fuer Screenshots — unabhaengig vom
Haupt-Scanner-Browser. Der Browser wird lazy beim ersten Screenshot
gestartet und fuer weitere Aufrufe offen gehalten.

Screenshots werden persistent auf Disk gecacht. Ein Eintrag gilt als frisch,
solange der vom Aufrufer mitgegebene HTTP-Validator (ETag bevorzugt, sonst
Last-Modified, sonst Content-Length) unveraendert ist; ohne verlaesslichen
Validator greift ein TTL-Fallback.

1:1 portiert aus sitemap-tracker.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import time
from pathlib import Path

from playwright.async_api import Browser, Playwright, async_playwright

_VIEWPORT = {"width": 1280, "height": 800}

CACHE_DIR = Path.home() / ".console-error-scanner" / "preview-cache"

_TTL_SECONDS = 14 * 24 * 3600


class PreviewService:
    """Erzeugt Seiten-Screenshots ueber eine eigene Playwright-Instanz."""

    def __init__(self, cache_dir: Path | None = None, ttl_seconds: int = _TTL_SECONDS) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._mem: dict[str, tuple[str, bytes]] = {}
        self._lock = asyncio.Lock()
        self._cache_dir = cache_dir or CACHE_DIR
        self._ttl = ttl_seconds

    async def capture(self, url: str, validator: str = "") -> bytes | None:
        """Liefert einen PNG-Screenshot der Seite (aus Cache, wenn frisch)."""
        cached = self._mem.get(url)
        if cached is not None and self._mem_fresh(cached[0], validator):
            return cached[1]

        async with self._lock:
            cached = self._mem.get(url)
            if cached is not None and self._mem_fresh(cached[0], validator):
                return cached[1]

            disk = self._load_disk(url, validator)
            if disk is not None:
                self._mem[url] = (validator, disk)
                return disk

            try:
                browser = await self._ensure_browser()
                page = await browser.new_page(viewport=_VIEWPORT, ignore_https_errors=True)  # type: ignore[arg-type]
                try:
                    await page.goto(url, wait_until="load", timeout=15000)
                    data = await page.screenshot(type="png")
                finally:
                    await page.close()
            except Exception:
                return None

        self._mem[url] = (validator, data)
        self._save_disk(url, validator, data)
        return data

    @staticmethod
    def _mem_fresh(stored_validator: str, validator: str) -> bool:
        """Session-Cache-Treffer gueltig? Ohne Validator immer (Session ist kurz)."""
        if not validator:
            return True
        return stored_validator == validator

    def _load_disk(self, url: str, validator: str) -> bytes | None:
        """Laedt einen Screenshot von Disk, sofern er frisch ist."""
        png = self._png_path(url)
        meta = self._meta_path(url)
        if not png.is_file() or not meta.is_file():
            return None
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            return None

        stored = str(info.get("validator", ""))
        if validator and stored:
            if stored != validator:
                return None
        else:
            try:
                captured = float(info.get("captured_at", 0))
            except (TypeError, ValueError):
                return None
            if (time.time() - captured) > self._ttl:
                return None

        try:
            return png.read_bytes()
        except Exception:
            return None

    def _save_disk(self, url: str, validator: str, data: bytes) -> None:
        """Schreibt Screenshot + Validator-Sidecar best-effort auf Disk."""
        with contextlib.suppress(Exception):
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._png_path(url).write_bytes(data)
            self._meta_path(url).write_text(
                json.dumps({"url": url, "validator": validator, "captured_at": time.time()}),
                encoding="utf-8",
            )

    def _png_path(self, url: str) -> Path:
        return self._cache_dir / f"{self._key(url)}.png"

    def _meta_path(self, url: str) -> Path:
        return self._cache_dir / f"{self._key(url)}.json"

    @staticmethod
    def _key(url: str) -> str:
        """Stabiler Dateiname-Schluessel aus der URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    async def _ensure_browser(self) -> Browser:
        """Startet den Sidecar-Browser beim ersten Aufruf."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox"],
            )
        return self._browser

    async def close(self) -> None:
        """Schliesst Browser und Playwright-Instanz best-effort."""
        if self._browser is not None:
            with contextlib.suppress(Exception):
                await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                await self._playwright.stop()
            self._playwright = None
