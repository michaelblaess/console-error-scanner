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
from collections.abc import Callable
from pathlib import Path

from playwright.async_api import Browser, Page, Playwright, async_playwright

# Typ fuer den optionalen Fortschritts-Callback. Bekommt einen semantischen
# Phasen-Schluessel ("navigate", "consent", "render", "capture"), den die UI
# uebersetzt und live anzeigt.
PhaseCallback = Callable[[str], None]

_VIEWPORT = {"width": 1280, "height": 800}

CACHE_DIR = Path.home() / ".console-error-scanner" / "preview-cache"

_TTL_SECONDS = 14 * 24 * 3600


class PreviewService:
    """Erzeugt Seiten-Screenshots ueber eine eigene Playwright-Instanz."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int = _TTL_SECONDS,
        proxy: str = "",
    ) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._mem: dict[str, tuple[str, bytes]] = {}
        self._lock = asyncio.Lock()
        self._cache_dir = cache_dir or CACHE_DIR
        self._ttl = ttl_seconds
        # Optionaler Corporate-Proxy (Zscaler) fuer den Sidecar-Browser.
        self._proxy = proxy.strip()

    async def capture(
        self, url: str, validator: str = "", on_phase: PhaseCallback | None = None
    ) -> bytes | None:
        """Liefert einen PNG-Screenshot der Seite (aus Cache, wenn frisch).

        Args:
            url:
                Die zu fotografierende URL.
            validator:
                Optionaler Cache-Validator aus der Scan-Antwort.
            on_phase:
                Optionaler Callback, der bei jedem Schritt der Live-Erzeugung
                einen Phasen-Schluessel bekommt ("navigate", "consent",
                "render", "capture"). Bei Cache-Treffern NICHT gerufen.

        Returns:
            PNG-Bilddaten oder None, wenn der Screenshot fehlschlaegt.
        """
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
                    self._emit(on_phase, "navigate")
                    await page.goto(url, wait_until="load", timeout=15000)
                    await self._prepare_page(page, on_phase)
                    self._emit(on_phase, "capture")
                    data = await page.screenshot(type="png")
                finally:
                    await page.close()
            except Exception:
                return None

        self._mem[url] = (validator, data)
        self._save_disk(url, validator, data)
        return data

    @staticmethod
    def _emit(on_phase: PhaseCallback | None, phase: str) -> None:
        """Ruft den Fortschritts-Callback best-effort auf."""
        if on_phase is None:
            return
        with contextlib.suppress(Exception):
            on_phase(phase)

    async def _prepare_page(self, page: Page, on_phase: PhaseCallback | None = None) -> None:
        """Bereitet die Seite fuer den Screenshot vor.

        Akzeptiert gaengige Cookie-Consent-Banner (sonst bleiben Hero-/
        Tracking-Bilder ggf. ungeladen), wartet auf networkidle (SPAs rendern
        Inhalt erst nach dem load-Event) und triggert Lazy-Loading. Ohne diese
        Schritte wird der Screenshot zu frueh gemacht und oben sichtbare Bilder
        fehlen.

        Args:
            page:
                Die bereits navigierte Playwright-Page.
            on_phase:
                Optionaler Fortschritts-Callback (siehe ``capture``).
        """
        self._emit(on_phase, "consent")
        await self._accept_consent(page)
        self._emit(on_phase, "render")
        await self._trigger_lazy_loading(page)

    @staticmethod
    async def _accept_consent(page: Page) -> None:
        """Akzeptiert gaengige Consent-Manager (Usercentrics/OneTrust/Cookiebot).

        Viele Seiten laden Tracking- und teils Hero-/Asset-Scripts erst nach
        dem Consent. Best-effort - schlaegt es fehl, faehrt der Screenshot fort.

        Args:
            page:
                Die navigierte Playwright-Page.
        """
        with contextlib.suppress(Exception):
            consent = await page.evaluate(
                """() => {
                    if (window.UC_UI && typeof window.UC_UI.acceptAllConsents === 'function') {
                        window.UC_UI.acceptAllConsents();
                        if (typeof window.UC_UI.closeCMP === 'function') { window.UC_UI.closeCMP(); }
                        return true;
                    }
                    if (window.OneTrust && typeof window.OneTrust.AllowAll === 'function') {
                        window.OneTrust.AllowAll();
                        return true;
                    }
                    if (window.Cookiebot && typeof window.Cookiebot.submitCustomConsent === 'function') {
                        window.Cookiebot.submitCustomConsent(true, true, true);
                        return true;
                    }
                    return false;
                }"""
            )
            if consent:
                await page.wait_for_timeout(1500)

    @staticmethod
    async def _trigger_lazy_loading(page: Page) -> None:
        """Scrollt die Seite durch und wartet, bis alle Bilder geladen sind.

        Wartet zuerst auf networkidle (JS-gerenderter Content steht erst danach),
        triggert dann IntersectionObserver-basiertes Lazy-Loading und pollt auf
        ``img.complete``. Best-effort - Fehler sind unkritisch.

        Args:
            page:
                Die navigierte Playwright-Page.
        """
        # Viele Seiten (SPAs) rendern ihren Inhalt erst nach dem load-Event per
        # JS nach - inkl. Hero-Bildern (oft CSS-Backgrounds, nicht <img>).
        # networkidle abwarten, damit der Content steht. Best-effort mit
        # Timeout, weil Seiten mit Dauerverbindungen sonst haengen wuerden.
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=8000)

        with contextlib.suppress(Exception):
            viewport_height = await page.evaluate("window.innerHeight")
            scroll_height = await page.evaluate("document.documentElement.scrollHeight")

            if scroll_height > viewport_height:
                current = 0
                while current < scroll_height:
                    current += viewport_height
                    await page.evaluate(f"window.scrollTo(0, {current})")
                    await page.wait_for_timeout(150)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(300)

            # Warten bis alle Bilder geladen (max ~3s Polling).
            for _ in range(12):
                all_loaded = await page.evaluate(
                    """() => {
                        const imgs = Array.from(document.querySelectorAll('img'));
                        return imgs.every(i => i.complete && i.naturalWidth > 0);
                    }"""
                )
                if all_loaded:
                    break
                await page.wait_for_timeout(250)

            # Extra-Settle fuer spaet getriggerte Bilder.
            await page.wait_for_timeout(500)

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
                proxy={"server": self._proxy} if self._proxy else None,
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
