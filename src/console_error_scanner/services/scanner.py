"""Scanner-Service - Kern-Logik fuer Website-Scanning mit Playwright."""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Optional
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from ..models.scan_result import ErrorType, PageError, PageStatus, ScanResult


class Scanner:
    """Scannt Webseiten auf Console-Errors und HTTP-Fehler.

    Verwendet Playwright (headless Chromium) fuer Browser-Automation.
    Unterstuetzt parallelen Scan mit konfigurierbarer Concurrency.
    """

    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 5

    # Realistischer Chrome User-Agent (kein HeadlessChrome, kein Playwright)
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    # Welche console.* Typen bei welchem Level erfasst werden
    CONSOLE_LEVELS = {
        "error": {"error"},
        "warn": {"error", "warning"},
        "all": {"error", "warning", "info", "log", "debug", "trace"},
    }

    def __init__(
        self,
        concurrency: int = 8,
        timeout: int = 30,
        headless: bool = True,
        console_level: str = "warn",
        user_agent: str = "",
        cookies: Optional[list[dict[str, str]]] = None,
        accept_consent: bool = True,
    ) -> None:
        self.concurrency = concurrency
        self.timeout = timeout
        self.headless = headless
        self.console_level = console_level
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.cookies = cookies or []
        self.accept_consent = accept_consent
        self._captured_types = self.CONSOLE_LEVELS.get(console_level, {"error", "warning"})
        self._cancelled = False
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def scan_urls(
        self,
        results: list[ScanResult],
        on_result: Optional[Callable[[ScanResult], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[ScanResult]:
        """Scannt alle URLs parallel mit Semaphore-Begrenzung.

        Args:
            results: Liste der ScanResult-Objekte (werden in-place aktualisiert).
            on_result: Callback fuer jedes einzelne Ergebnis.
            on_log: Callback fuer Log-Nachrichten.
            on_progress: Callback fuer Fortschritt (aktuell, gesamt).

        Returns:
            Die uebergebene Liste der ScanResults.
        """
        self._cancelled = False
        total = len(results)
        semaphore = asyncio.Semaphore(self.concurrency)
        completed = 0

        def log(msg: str) -> None:
            if on_log:
                on_log(msg)

        log(f"Starte Scan von {total} URLs (Concurrency: {self.concurrency}, Timeout: {self.timeout}s)")

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._launch_browser()
            log("Browser gestartet")

            async def scan_with_semaphore(result: ScanResult, index: int) -> None:
                nonlocal completed
                if self._cancelled:
                    return

                async with semaphore:
                    if self._cancelled:
                        return

                    result.status = PageStatus.SCANNING
                    if on_result:
                        on_result(result)

                    log(f"Scanne ({index + 1}/{total}): {result.url}")
                    await self._scan_single_page(result, log)
                    completed += 1

                    if on_result:
                        on_result(result)
                    if on_progress:
                        on_progress(completed, total)

                    status_text = result.status_icon
                    error_info = ""
                    if result.has_issues:
                        error_info = f" | {result.total_error_count} Fehler"
                    log(f"  [{status_text}] {result.url} ({result.load_time_ms / 1000:.1f}s){error_info}")

            tasks = [
                scan_with_semaphore(result, idx)
                for idx, result in enumerate(results)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            log(f"[red]Kritischer Fehler: {e}[/red]")
        finally:
            await self._cleanup()
            log("Browser geschlossen")

        return results

    async def _scan_single_page(
        self,
        result: ScanResult,
        log: Callable[[str], None],
    ) -> None:
        """Scannt eine einzelne Seite mit Retry-Logik.

        Args:
            result: ScanResult das befuellt wird.
            log: Logging-Callback.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                await self._do_scan_page(result, log)
                return
            except Exception as e:
                result.retry_count = attempt + 1
                error_msg = str(e)

                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.BACKOFF_BASE_SECONDS * (2 ** attempt)
                    log(f"  Retry {attempt + 1}/{self.MAX_RETRIES} fuer {result.url} in {wait_time}s ({error_msg})")

                    # Netzwerk-Check vor Retry
                    if not await self._check_network():
                        log("  Warte auf Netzwerk...")
                        await self._wait_for_network(max_wait=wait_time * 2)

                    await asyncio.sleep(wait_time)

                    # Browser-Recovery falls noetig
                    if not self._browser or not self._browser.is_connected():
                        log("  Browser-Recovery...")
                        try:
                            self._browser = await self._launch_browser()
                        except Exception as browser_err:
                            log(f"  Browser-Recovery fehlgeschlagen: {browser_err}")
                else:
                    # Letzter Versuch fehlgeschlagen
                    result.status = PageStatus.TIMEOUT if "timeout" in error_msg.lower() else PageStatus.ERROR
                    log(f"  [bold red]Fehlgeschlagen nach {self.MAX_RETRIES} Versuchen: {error_msg}[/bold red]")

    async def _do_scan_page(
        self,
        result: ScanResult,
        log: Callable[[str], None] = lambda _: None,
    ) -> None:
        """Fuehrt den eigentlichen Scan einer Seite durch.

        Args:
            result: ScanResult das mit Fehlern befuellt wird.
            log: Logging-Callback fuer Debug-Ausgaben.
        """
        if not self._browser or not self._browser.is_connected():
            raise RuntimeError("Browser nicht verbunden")

        context = await self._browser.new_context(
            ignore_https_errors=True,
            java_script_enabled=True,
            user_agent=self.user_agent,
        )

        # Custom Cookies setzen (z.B. Auth-Cookies fuer Test-Umgebungen)
        if self.cookies:
            parsed = urlparse(result.url)
            domain = parsed.hostname or ""
            cookie_list = [
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": domain,
                    "path": "/",
                }
                for c in self.cookies
            ]
            await context.add_cookies(cookie_list)

        page = await context.new_page()

        try:
            page.set_default_timeout(self.timeout * 1000)

            # CDP-Session fuer Browser-interne Meldungen:
            # - CSP-Violations (Audits-Domain, "Issues"-Tab in DevTools)
            # - Security/Intervention/Deprecation (Log-Domain)
            # CSP-Violations werden in modernem Chromium ueber das Audits-Domain
            # gemeldet, NICHT ueber Log, Console oder DOM-Events.
            cdp_client = await context.new_cdp_session(page)
            await cdp_client.send("Log.enable")
            await cdp_client.send("Audits.enable")

            def on_cdp_issue(params):
                """Handler fuer Audits.issueAdded - faengt CSP-Violations."""
                issue = params.get("issue", {})
                code = issue.get("code", "")
                log(f"    [dim][CDP Audits] code={code}[/dim]")
                details = issue.get("details", {})

                if code == "ContentSecurityPolicyIssue":
                    csp = details.get("contentSecurityPolicyIssueDetails", {})
                    directive = csp.get("violatedDirective", "")
                    blocked_url = csp.get("blockedURL", "")
                    is_report_only = csp.get("isReportOnly", False)
                    violation_type = csp.get("contentSecurityPolicyViolationType", "")

                    # Quell-Position extrahieren
                    source_loc = csp.get("sourceCodeLocation", {})
                    source_url = source_loc.get("url", "")
                    source_line = source_loc.get("lineNumber", 0)

                    prefix = "CSP report-only" if is_report_only else "CSP violation"
                    msg = f"{prefix}: '{directive}'"
                    if blocked_url:
                        msg += f" blocked {blocked_url}"

                    result.errors.append(PageError(
                        error_type=ErrorType.CONSOLE_WARNING,
                        message=msg,
                        source=source_url or blocked_url,
                        line_number=source_line,
                    ))

            cdp_client.on("Audits.issueAdded", on_cdp_issue)

            def on_cdp_log(params):
                """Handler fuer Log.entryAdded - faengt Security/Intervention."""
                entry = params.get("entry", {})
                text = entry.get("text", "")
                source = entry.get("source", "")
                url = entry.get("url", "")
                line = entry.get("lineNumber", 0)
                log(f"    [dim][CDP Log] source={source} text={text[:80]}[/dim]")

                if source in ("security", "violation"):
                    result.errors.append(PageError(
                        error_type=ErrorType.CONSOLE_WARNING,
                        message=f"CSP violation: {text}",
                        source=url,
                        line_number=line,
                    ))
                elif source == "intervention":
                    result.errors.append(PageError(
                        error_type=ErrorType.CONSOLE_WARNING,
                        message=f"Intervention: {text}",
                        source=url,
                        line_number=line,
                    ))
                elif source == "deprecation":
                    if self.console_level == "all":
                        result.errors.append(PageError(
                            error_type=ErrorType.CONSOLE_WARNING,
                            message=f"Deprecation: {text}",
                            source=url,
                            line_number=line,
                        ))

            cdp_client.on("Log.entryAdded", on_cdp_log)

            # Console-Handler registrieren (Level abhaengig von console_level)
            captured_types = self._captured_types

            def on_console(msg):
                msg_type = msg.type
                text = msg.text or ""
                log(f"    [dim][Console {msg_type}] {text[:100]}[/dim]")
                if msg_type not in captured_types:
                    return

                # "Failed to load resource" ueberspringen - HTTP-Fehler werden
                # bereits ueber den Response-Handler erfasst (vermeidet Doubletten)
                if text.startswith("Failed to load resource:"):
                    return

                location = msg.location or {}

                # error -> CONSOLE_ERROR, alles andere -> CONSOLE_WARNING
                error_type = ErrorType.CONSOLE_ERROR if msg_type == "error" else ErrorType.CONSOLE_WARNING

                result.errors.append(PageError(
                    error_type=error_type,
                    message=text,
                    source=location.get("url", ""),
                    line_number=location.get("lineNumber", 0),
                ))

            page.on("console", on_console)

            # Uncaught Exceptions Handler (TypeError, ReferenceError, etc.)
            # Diese erscheinen im Browser als "Uncaught TypeError: ..."
            # und werden NICHT ueber page.on("console") erfasst!
            def on_pageerror(error):
                error_msg = str(error) if error else "(unknown error)"
                result.errors.append(PageError(
                    error_type=ErrorType.CONSOLE_ERROR,
                    message=error_msg,
                    source="",
                    line_number=0,
                ))

            page.on("pageerror", on_pageerror)

            # HTTP-Fehler Handler registrieren
            def on_response(response):
                status = response.status
                url = response.url

                # Haupt-Seiten-Status merken
                if response.request.resource_type == "document":
                    result.http_status_code = status

                if status == 404:
                    result.errors.append(PageError(
                        error_type=ErrorType.HTTP_404,
                        message=f"HTTP 404: {url}",
                        source=url,
                    ))
                elif 400 <= status < 500:
                    result.errors.append(PageError(
                        error_type=ErrorType.HTTP_4XX,
                        message=f"HTTP {status}: {url}",
                        source=url,
                    ))
                elif 500 <= status < 600:
                    result.errors.append(PageError(
                        error_type=ErrorType.HTTP_5XX,
                        message=f"HTTP {status}: {url}",
                        source=url,
                    ))

            page.on("response", on_response)

            # Fehlgeschlagene Requests (CSP-Blockierungen, Netzwerkfehler etc.)
            def on_request_failed(request):
                failure = request.failure
                if not failure:
                    return
                failure_text = failure or ""
                url = request.url
                log(f"    [dim][ReqFail] {failure_text} - {url[:80]}[/dim]")
                # Nur relevante Fehler erfassen, nicht Abbrueche durch Navigation
                if "net::ERR_ABORTED" in failure_text:
                    return
                result.errors.append(PageError(
                    error_type=ErrorType.CONSOLE_WARNING,
                    message=f"Request failed: {failure_text} - {url}",
                    source=url,
                    line_number=0,
                ))

            page.on("requestfailed", on_request_failed)

            # Seite laden
            start_time = time.monotonic()
            response = await page.goto(
                result.url,
                wait_until="networkidle",
                timeout=self.timeout * 1000,
            )
            elapsed = time.monotonic() - start_time
            result.load_time_ms = int(elapsed * 1000)

            if response:
                result.http_status_code = response.status

            # Consent-Banner behandeln (akzeptieren oder nur verstecken)
            if self.accept_consent:
                await self._accept_consent(page, log)
            else:
                # Nur Banner verstecken, NICHT akzeptieren
                log("    Consent-Banner versteckt (kein Consent akzeptiert)")
                await self._hide_consent_banners(page)
                await page.wait_for_timeout(1000)

            # Doubletten entfernen: gleiche (error_type, message, source) nur einmal
            seen = set()
            unique_errors = []
            for error in result.errors:
                key = (error.error_type, error.message, error.source)
                if key not in seen:
                    seen.add(key)
                    unique_errors.append(error)
            result.errors = unique_errors

            if result.has_errors:
                result.status = PageStatus.ERROR
            elif result.has_issues:
                result.status = PageStatus.WARNING
            else:
                result.status = PageStatus.OK

        finally:
            # CDP-Session sauber schliessen
            try:
                await cdp_client.detach()
            except Exception:
                pass
            await context.close()

    async def _accept_consent(
        self,
        page: Page,
        log: Callable[[str], None] = lambda _: None,
    ) -> None:
        """Akzeptiert Cookie-Consent-Banner automatisch (3 Phasen).

        Phase 1: JavaScript-APIs (Usercentrics, OneTrust, CookieBot).
        Phase 2: Button-Klick Fallback (16 Selektoren).
        Phase 3: CSS-Hide (immer).

        Args:
            page: Die Playwright-Page.
            log: Logging-Callback.
        """
        # Phase 1: JavaScript-API aufrufen
        try:
            consent_result = await page.evaluate("""() => {
                // Usercentrics
                if (window.UC_UI && typeof window.UC_UI.acceptAllConsents === 'function') {
                    window.UC_UI.acceptAllConsents();
                    return 'usercentrics';
                }
                // OneTrust
                if (window.OneTrust && typeof window.OneTrust.AllowAll === 'function') {
                    window.OneTrust.AllowAll();
                    return 'onetrust';
                }
                // CookieBot
                if (window.Cookiebot && typeof window.Cookiebot.submitCustomConsent === 'function') {
                    window.Cookiebot.submitCustomConsent(true, true, true);
                    return 'cookiebot';
                }
                return null;
            }""")
            if consent_result:
                log(f"    Consent akzeptiert ({consent_result})")
                await page.wait_for_timeout(2000)
                # Banner verstecken als Sicherheit
                await self._hide_consent_banners(page)
                return
        except Exception:
            pass

        # Phase 2: Fallback - Consent-Buttons per Klick akzeptieren
        consent_selectors = [
            # Usercentrics Buttons
            '[data-testid="uc-accept-all-button"]',
            '#uc-btn-accept-banner',
            '.uc-btn-accept',
            # OneTrust Buttons
            '#onetrust-accept-btn-handler',
            '.onetrust-close-btn-handler',
            # CookieBot Buttons
            '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
            '#CybotCookiebotDialogBodyButtonAccept',
            # Generische Consent-Buttons
            '[data-cookie-accept]',
            '[data-consent-accept]',
            'button[class*="accept"]',
            'button[class*="consent"]',
            'a[class*="accept"]',
            '.cookie-accept',
            '.cookie-consent-accept',
            '#cookie-accept',
            '#accept-cookies',
            '.cc-accept',
            '.cc-btn.cc-allow',
        ]

        clicked = False
        for selector in consent_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=500):
                    await button.click(timeout=2000)
                    log(f"    Consent-Button geklickt: {selector}")
                    clicked = True
                    break
            except Exception:
                continue

        if clicked:
            await page.wait_for_timeout(2000)

        # Phase 3: Banner per CSS verstecken (immer)
        await self._hide_consent_banners(page)

        if not clicked:
            await page.wait_for_timeout(1000)

    async def _hide_consent_banners(self, page: Page) -> None:
        """Versteckt gaengige Consent-Banner per CSS display:none.

        Behandelt 16 Selektoren, Usercentrics Shadow DOM
        und setzt body.overflow zurueck.

        Args:
            page: Die Playwright-Page.
        """
        try:
            await page.evaluate("""() => {
                var selectors = [
                    '#usercentrics-root',
                    '#uc-banner',
                    '.uc-banner',
                    '#onetrust-banner-sdk',
                    '#onetrust-consent-sdk',
                    '#CybotCookiebotDialog',
                    '#CybotCookiebotDialogBodyUnderlay',
                    '.cookie-banner',
                    '.cookie-consent',
                    '.cookie-notice',
                    '[class*="cookie-banner"]',
                    '[class*="cookie-consent"]',
                    '[id*="cookie-banner"]',
                    '[id*="cookie-consent"]',
                    '[class*="consent-banner"]',
                    '[class*="CookieConsent"]',
                ];
                selectors.forEach(function(sel) {
                    try {
                        var els = document.querySelectorAll(sel);
                        els.forEach(function(el) { el.style.display = 'none'; });
                    } catch(e) {}
                });

                // Usercentrics Shadow DOM
                var ucRoot = document.getElementById('usercentrics-root');
                if (ucRoot && ucRoot.shadowRoot) {
                    var shadowBanners = ucRoot.shadowRoot.querySelectorAll('[class*="banner"]');
                    shadowBanners.forEach(function(el) { el.style.display = 'none'; });
                }

                // Body Overflow zuruecksetzen (Consent-Banner blockieren oft Scrollen)
                document.body.style.overflow = '';
                document.documentElement.style.overflow = '';
            }""")
        except Exception:
            pass

    async def _launch_browser(self) -> Browser:
        """Startet den Chromium-Browser.

        Returns:
            Playwright Browser-Instanz.
        """
        return await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

    async def _check_network(self) -> bool:
        """Prueft ob das Netzwerk erreichbar ist.

        Returns:
            True wenn Netzwerk verfuegbar.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                response = await client.head("https://www.google.com")
                return response.status_code < 500
        except Exception:
            return False

    async def _wait_for_network(self, max_wait: int = 60) -> None:
        """Wartet bis das Netzwerk wieder verfuegbar ist.

        Args:
            max_wait: Maximale Wartezeit in Sekunden.
        """
        start = time.monotonic()
        while time.monotonic() - start < max_wait:
            if await self._check_network():
                return
            await asyncio.sleep(2)

    def cancel(self) -> None:
        """Bricht den laufenden Scan ab."""
        self._cancelled = True

    async def _cleanup(self) -> None:
        """Rauemt Browser und Playwright auf."""
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._browser = None
        self._playwright = None
