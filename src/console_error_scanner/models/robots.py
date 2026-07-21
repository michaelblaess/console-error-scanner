"""robots.txt-Auswertung: prueft, ob eine Seite abgerufen werden darf.

Geprueft werden nur die SEITEN aus der Sitemap. Ressourcen, die eine Seite
nachlaedt (Bilder, Skripte), werden bewusst nicht geprueft: sie liegen oft auf
einer CDN-Domain mit eigener robots.txt, und wer die Seite ausliefern darf,
liefert ihre Ressourcen ohnehin mit aus.

Ausgewertet wird nur der `User-agent: *`-Block; der Scanner tritt nicht unter
einem eigenen Bot-Namen auf.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import httpx


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Uebersetzt ein robots-Pfadmuster in eine Regex.

    Der Standard (RFC 9309) kennt zwei Sonderzeichen: `*` fuer eine beliebige
    Zeichenfolge und `$` am Ende fuer "Pfad endet hier". Ohne diese Behandlung
    greifen reale Regeln wie `Disallow: /*CR-Dokumentation.pdf$` nie, weil kein
    Pfad buchstaeblich mit `/*CR-` beginnt.

    Args:
        pattern:
        Pfadmuster aus einer Disallow-/Allow-Zeile.

    Returns:
        Kompilierte Regex, die am Pfadanfang ankert.
    """
    anchored_end = pattern.endswith("$")
    raw = pattern[:-1] if anchored_end else pattern
    body = "".join(".*" if char == "*" else re.escape(char) for char in raw)
    return re.compile(f"^{body}$" if anchored_end else f"^{body}")


class RobotsChecker:
    """Laedt und parst die robots.txt einer Domain (Disallow/Allow)."""

    def __init__(self) -> None:
        # (Musterlaenge, kompiliertes Muster, erlaubt) - die Laenge entscheidet,
        # welche Regel bei mehreren Treffern gewinnt (spezifischste zuerst).
        self._rules: list[tuple[int, re.Pattern[str], bool]] = []
        self._loaded = False

    async def load(
        self,
        base_url: str,
        cookies: list[dict[str, str]] | None = None,
        proxy: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Laedt die robots.txt zur angegebenen URL.

        Nicht erreichbar oder kein 200 = keine Regeln = alles erlaubt. Das ist
        bewusst die freundliche Auslegung: ein fehlendes robots.txt ist keine
        Sperre.

        Args:
            base_url:
            Beliebige URL der Zieldomain; daraus wird /robots.txt abgeleitet.
            cookies:
            Optionale Cookies (z.B. fuer geschuetzte Testsysteme).
            proxy:
            Optionale Proxy-URL (Corporate-Proxy/Zscaler).
            client:
            Optionaler, bereits konfigurierter Client - sonst wird einer
            geoeffnet. Dient vor allem der Testbarkeit ohne Netzwerk.
        """
        parsed = urlparse(base_url)
        robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))

        try:
            if client is not None:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    self._parse(response.text)
            else:
                jar = httpx.Cookies()
                for cookie in cookies or []:
                    jar.set(cookie["name"], cookie["value"])
                async with httpx.AsyncClient(
                    timeout=10.0,
                    follow_redirects=True,
                    verify=False,
                    cookies=jar,
                    proxy=proxy.strip() or None,
                ) as own_client:
                    response = await own_client.get(robots_url)
                    if response.status_code == 200:
                        self._parse(response.text)
        except Exception:  # noqa: BLE001 - robots.txt ist optional
            pass
        self._loaded = True

    def _parse(self, text: str) -> None:
        """Parst Disallow/Allow aus dem `User-agent: *`-Block."""
        in_wildcard_block = False

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if "#" in line:
                line = line[: line.index("#")].strip()
            if not line:
                continue

            lower = line.lower()
            if lower.startswith("user-agent:"):
                in_wildcard_block = line[len("user-agent:") :].strip() == "*"
                continue
            if not in_wildcard_block:
                continue

            if lower.startswith("disallow:"):
                path = line[len("disallow:") :].strip()
                if path:  # "Disallow:" ohne Pfad heisst: alles erlaubt
                    self._rules.append((len(path), _compile_pattern(path), False))
            elif lower.startswith("allow:"):
                path = line[len("allow:") :].strip()
                if path:
                    self._rules.append((len(path), _compile_pattern(path), True))

    def is_allowed(self, url: str) -> bool:
        """Prueft, ob die URL abgerufen werden darf.

        Bei mehreren passenden Regeln gewinnt die laengste (spezifischste); bei
        gleicher Laenge gewinnt Allow - so schreibt es RFC 9309 vor.
        """
        if not self._rules:
            return True

        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        best_length = -1
        allowed = True
        for length, pattern, rule_allows in self._rules:
            if not pattern.search(path):
                continue
            if length > best_length or (length == best_length and rule_allows):
                best_length = length
                allowed = rule_allows
        return allowed

    @property
    def is_loaded(self) -> bool:
        """Gibt zurueck, ob ein Ladeversuch stattgefunden hat."""
        return self._loaded
