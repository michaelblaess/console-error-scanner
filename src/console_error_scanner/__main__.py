"""Entry Point fuer Console Error Scanner."""

from __future__ import annotations

import argparse
import os
import sys

# Frozen-EXE Erkennung (PyInstaller):
# PLAYWRIGHT_BROWSERS_PATH muss gesetzt werden BEVOR playwright importiert wird,
# damit das gebundelte Chromium im "browsers"-Unterordner gefunden wird.
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(sys.executable)
    _browsers_dir = os.path.join(_exe_dir, "browsers")
    if os.path.isdir(_browsers_dir):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _browsers_dir

from . import __version__
from .app import ConsoleErrorScannerApp


BANNER = f"""
  Console Error Scanner v{__version__}
  Scannt Websites auf Console-Errors und HTTP-Fehler (404, 5xx)
"""

USAGE_EXAMPLES = """
Beispiele:
  console-error-scanner https://example.com/sitemap.xml
  console-error-scanner https://example.com/sitemap.xml --concurrency 12
  console-error-scanner https://example.com/sitemap.xml --output-html report.html
  console-error-scanner https://example.com/sitemap.xml --console-level error
  console-error-scanner https://example.com/sitemap.xml --filter /produkte
  console-error-scanner https://test.example.com/sitemap.xml --cookie auth=token123
  console-error-scanner https://example.com/sitemap.xml --whitelist whitelist.json

Tastenkuerzel in der TUI:
  s = Scan starten    r = Reports speichern    t = Top 10 Fehler
  h = History         l = Log ein/aus          e = Nur Fehler
  n = Consent-Toggle  / = Filter               + / - = Log-Hoehe
  i = Info            q = Beenden
"""


def main() -> None:
    """Haupteinstiegspunkt fuer die CLI."""
    parser = argparse.ArgumentParser(
        prog="console-error-scanner",
        description=BANNER,
        epilog=USAGE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "sitemap_url",
        nargs="?",
        default="",
        metavar="SITEMAP_URL",
        help="URL der Sitemap (XML)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=8,
        metavar="N",
        help="Max parallele Browser-Tabs (default: 8)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        metavar="SEC",
        help="Timeout pro Seite in Sekunden (default: 30)",
    )
    parser.add_argument(
        "--output-json",
        default="",
        metavar="PATH",
        help="JSON-Report automatisch speichern",
    )
    parser.add_argument(
        "--output-html",
        default="",
        metavar="PATH",
        help="HTML-Report automatisch speichern",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        default=False,
        help="Browser sichtbar starten (Debugging)",
    )
    parser.add_argument(
        "--filter", "-f",
        default="",
        metavar="TEXT",
        help="Nur URLs scannen die TEXT enthalten",
    )
    parser.add_argument(
        "--console-level",
        default="warn",
        choices=["error", "warn", "all"],
        metavar="LEVEL",
        help="Console-Level: error | warn (default) | all",
    )
    parser.add_argument(
        "--user-agent",
        default="",
        metavar="UA",
        help="Custom User-Agent String (default: Chrome 131)",
    )
    parser.add_argument(
        "--cookie",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Cookie setzen (z.B. --cookie auth=token). Mehrfach verwendbar.",
    )
    parser.add_argument(
        "--whitelist", "-w",
        default="",
        metavar="PATH",
        help="Pfad zur Whitelist-JSON (bekannte Fehler ignorieren)",
    )
    parser.add_argument(
        "--no-consent",
        action="store_true",
        default=None,
        help="Cookie-Consent NICHT akzeptieren (Banner wird nur versteckt)",
    )

    args = parser.parse_args()

    # Cookies parsen: "NAME=VALUE" -> {"name": "NAME", "value": "VALUE"}
    cookies = []
    for cookie_str in args.cookie:
        if "=" not in cookie_str:
            print(f"Ungueltig: --cookie {cookie_str} (Format: NAME=VALUE)")
            sys.exit(1)
        name, value = cookie_str.split("=", 1)
        cookies.append({"name": name.strip(), "value": value.strip()})

    app = ConsoleErrorScannerApp(
        sitemap_url=args.sitemap_url,
        concurrency=args.concurrency,
        timeout=args.timeout,
        output_json=args.output_json,
        output_html=args.output_html,
        headless=not args.no_headless,
        url_filter=args.filter,
        console_level=args.console_level,
        user_agent=args.user_agent,
        cookies=cookies,
        whitelist_path=args.whitelist,
        accept_consent=not args.no_consent if args.no_consent is not None else None,
    )
    app.run()


if __name__ == "__main__":
    main()
