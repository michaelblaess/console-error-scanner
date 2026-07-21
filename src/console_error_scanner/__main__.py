"""Entry Point fuer Console Error Scanner."""

from __future__ import annotations

import argparse
import os
import sys

# Frozen-EXE Erkennung (PyInstaller UND Nuitka):
# PLAYWRIGHT_BROWSERS_PATH muss gesetzt werden BEVOR playwright importiert wird,
# damit das gebundelte Chromium im "browsers"-Unterordner gefunden wird.
_is_frozen = getattr(sys, "frozen", False) or "__compiled__" in globals()
if _is_frozen:
    _exe_dir = os.path.dirname(sys.executable)
    _browsers_dir = os.path.join(_exe_dir, "browsers")
    if os.path.isdir(_browsers_dir):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _browsers_dir

from textual_widgets import reset_terminal_title, set_terminal_title

from console_error_scanner import __version__
from console_error_scanner.i18n import SUPPORTED_LANGUAGES, load_locale
from console_error_scanner.models.settings import Settings


def _silence_proactor_teardown_noise() -> None:
    """Unterdrueckt das bekannte Windows-asyncio-Teardown-Rauschen.

    Auf Windows finalisiert der ProactorEventLoop die Subprocess-/Pipe-
    Transports des Playwright-Chromium teilweise erst per Garbage-Collector
    NACH dem (sauberen) App-Ende. Deren ``__del__`` wirft dann
    'unclosed transport' (ResourceWarning) bzw. 'I/O operation on closed pipe'
    (ValueError) - reines kosmetisches Rauschen, das ueber ``sys.unraisablehook``
    auf stderr landet. Wir schlucken GENAU diese Faelle; alles andere geht
    unveraendert an den Original-Hook (keine echten Fehler werden versteckt).
    """
    if sys.platform != "win32":
        return
    original = sys.unraisablehook

    def _hook(unraisable: sys.UnraisableHookArgs) -> None:
        text = f"{unraisable.err_msg or ''} {unraisable.exc_value or ''}"
        if "closed pipe" in text or "unclosed transport" in text:
            return
        original(unraisable)

    sys.unraisablehook = _hook


def main() -> None:
    """Haupteinstiegspunkt fuer die CLI."""
    _silence_proactor_teardown_noise()

    settings = Settings.load()
    saved_lang = settings.language

    parser = argparse.ArgumentParser(
        prog="console-error-scanner",
        description=f"\n  Console Error Scanner v{__version__}\n",
        epilog=_usage_examples(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "sitemap_url",
        nargs="?",
        default="",
        metavar="URL_OR_FILE",
        help=(
            "URL der Website, Sitemap-URL oder lokale sitemap.xml. "
            "Bei Domain-URLs wird die Sitemap automatisch gesucht. "
            "Ohne Argument fragt die App die URL beim ersten 's' ab."
        ),
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=None,
        metavar="N",
        help="Max parallele Browser-Tabs (Default aus Settings)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=None,
        metavar="SEC",
        help="Timeout pro Seite in Sekunden (Default aus Settings)",
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
        "--filter",
        "-f",
        default="",
        metavar="TEXT",
        help="Nur URLs scannen die TEXT enthalten",
    )
    parser.add_argument(
        "--console-level",
        default="",
        choices=["", "error", "warn", "all"],
        metavar="LEVEL",
        help="Console-Level: error | warn | all (Default aus Settings)",
    )
    parser.add_argument(
        "--user-agent",
        default="",
        metavar="UA",
        help="Custom User-Agent String (Default: realistischer Chrome)",
    )
    parser.add_argument(
        "--cookie",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Cookie setzen (mehrfach moeglich). Default aus Settings.",
    )
    parser.add_argument(
        "--whitelist",
        "-w",
        default="",
        metavar="PATH",
        help="Pfad zur Whitelist-JSON (Default aus Settings)",
    )
    parser.add_argument(
        "--no-consent",
        action="store_true",
        default=None,
        help="Cookie-Consent NICHT akzeptieren (nur Banner verstecken)",
    )
    parser.add_argument(
        "--no-scroll",
        action="store_true",
        default=None,
        help="Seite nicht scrollen (kein Lazy-Loading-Trigger)",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        default=None,
        help="robots.txt ignorieren (nur fuer eigene Seiten sinnvoll)",
    )
    parser.add_argument(
        "--lang",
        default=saved_lang,
        choices=SUPPORTED_LANGUAGES,
        help=f"Language ({', '.join(SUPPORTED_LANGUAGES)})",
    )

    args = parser.parse_args()

    # Sprache laden (CLI > Settings > Default)
    lang = args.lang
    load_locale(lang)

    # Sprache persistent speichern wenn per CLI geaendert
    if lang != saved_lang:
        settings.language = lang
        settings.save()

    # Cookies parsen: "NAME=VALUE" -> {"name": "NAME", "value": "VALUE"}
    cookies = []
    for cookie_str in args.cookie:
        if "=" not in cookie_str:
            from console_error_scanner.i18n import t

            print(t("cli.invalid_cookie", cookie=cookie_str))
            sys.exit(1)
        name, value = cookie_str.split("=", 1)
        cookies.append({"name": name.strip(), "value": value.strip()})

    # textual-image (TGP/Sixel) eager initialisieren, sobald das Terminal
    # Grafik-faehig ist - egal ob Vorschau aktuell an oder aus ist. Sonst
    # leaken die DA1-/Cell-Size-Query-Antworten beim spaeteren Aktivieren der
    # Vorschau in den fokussierten Input (Filter-Suche).
    _preinit_graphics_backend()

    # App NACH load_locale importieren - t() ist sofort verfuegbar
    from console_error_scanner.app import ConsoleErrorScannerApp

    set_terminal_title(f"✗ console-error-scanner v{__version__}")
    try:
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
            accept_consent=(not args.no_consent) if args.no_consent is not None else None,
            trigger_lazy_load=(not args.no_scroll) if args.no_scroll is not None else None,
            respect_robots=(not args.ignore_robots) if args.ignore_robots is not None else None,
        )
        app.run()
    finally:
        reset_terminal_title()


def _preinit_graphics_backend() -> None:
    """Eager-Import textual-image vor App-Start.

    textual-image sendet beim Import Escape-Queries ans Terminal (DA1
    Primary Device Attributes, Cell-Size-Query). Diese MUESSEN vor
    `App.run()` laufen, damit die Antworten von der Library konsumiert
    werden und nicht in Textual-Inputs landen (typischer Effekt: kryptische
    `[?61;...c<35;...M`-Strings im Filter-Eingabefeld).

    Wir laufen NUR, wenn das Terminal ueberhaupt ein Grafik-Protokoll
    unterstuetzen koennte (TGP/Sixel) - sonst spart das den Import auf
    "dummen" Terminals (SSH ohne Mux, dumb-tty etc.).
    """
    if not _terminal_supports_graphics():
        return
    try:
        import time

        import textual_image.renderable  # noqa: F401
        import textual_image.widget  # noqa: F401
        from textual_image._terminal import get_cell_size

        get_cell_size()
        # Kurze Pause, damit das Terminal Zeit hat die Probe-Queries zu
        # beantworten BEVOR Textual stdin uebernimmt - sonst hat man die
        # Antworten zwar abgeschickt, sie kommen aber erst zurueck wenn
        # der Cooked-Mode schon zu ist (Windows Terminal/mintty sind hier
        # spuerbar langsamer als ein lokales xterm).
        time.sleep(0.15)
    except Exception:
        pass


def _terminal_supports_graphics() -> bool:
    """Schnelle Heuristik: kann das Terminal evtl. TGP oder Sixel?"""
    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if os.environ.get("KITTY_WINDOW_ID"):
        return True
    if "kitty" in term or "ghostty" in term:
        return True
    if term_program in ("wezterm", "ghostty", "mintty", "iterm.app"):
        return True
    if os.environ.get("KONSOLE_VERSION"):
        return True
    if os.environ.get("WT_SESSION"):
        return True
    return term in ("foot", "xterm", "mlterm", "mintty") or "foot" in term


def _usage_examples() -> str:
    """Gibt die Nutzungsbeispiele zurueck."""
    return """
Examples:
  console-error-scanner https://example.com
  console-error-scanner https://example.com/sitemap.xml
  console-error-scanner sitemap.xml
  console-error-scanner https://example.com --concurrency 12
  console-error-scanner https://example.com --lang en

Keybindings (TUI):
  c = Crawl       m = Load sitemap   r = Report     h = History    s = Settings
  w = Whitelist   e = Errors only    t = Theme      l = Log
  d = Copy detail F10 = Top 10       / = Filter     i = Info       q = Quit
"""


if __name__ == "__main__":
    main()
