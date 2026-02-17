# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller Spec fuer Console Error Scanner.

Baut eine Standalone-EXE (--onedir) mit allen Abhaengigkeiten.
Playwright-Driver (node.exe + cli.js) wird eingebettet.
Chromium-Browser wird separat per build.bat in den dist-Ordner kopiert.

Ausfuehren: pyinstaller console-error-scanner.spec
"""

import os
import importlib

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Pfade ermitteln
playwright_pkg = os.path.dirname(importlib.import_module("playwright").__file__)
playwright_driver = os.path.join(playwright_pkg, "driver")

src_pkg = os.path.join("src", "console_error_scanner")

a = Analysis(
    [os.path.join(src_pkg, "__main__.py")],
    pathex=["src"],
    binaries=[],
    datas=[
        # App-eigene Dateien
        (os.path.join(src_pkg, "app.tcss"), "console_error_scanner"),

        # Playwright Driver (node.exe + package/)
        # Wird nach playwright/driver/ kopiert, wo das Python-Paket ihn erwartet
        (playwright_driver, os.path.join("playwright", "driver")),
    ],
    hiddenimports=[
        "console_error_scanner",
        "console_error_scanner.__main__",
        "console_error_scanner.app",
        "console_error_scanner.models",
        "console_error_scanner.models.scan_result",
        "console_error_scanner.models.sitemap",
        "console_error_scanner.models.whitelist",
        "console_error_scanner.widgets",
        "console_error_scanner.widgets.results_table",
        "console_error_scanner.widgets.summary_panel",
        "console_error_scanner.widgets.error_detail_view",
        "console_error_scanner.screens",
        "console_error_scanner.screens.error_detail",
        "console_error_scanner.screens.top_errors",
        "console_error_scanner.screens.about",
        "console_error_scanner.services",
        "console_error_scanner.services.scanner",
        "console_error_scanner.services.reporter",
        # Textual braucht diverse versteckte Imports
        "textual",
        "textual.app",
        "textual.widgets",
        "textual.widgets._data_table",
        "textual.widgets._header",
        "textual.widgets._footer",
        "textual.widgets._input",
        "textual.widgets._static",
        "textual.widgets._rich_log",
        "textual.containers",
        "textual.screen",
        "textual.binding",
        "textual.css",
        "textual.css.query",
        "textual._xterm_parser",
        "textual._win_sleep",
        # Rich
        "rich",
        "rich.text",
        "rich.markup",
        "rich.highlighter",
    ] + collect_submodules("rich._unicode_data") + [
        # Async/Networking
        "httpx",
        "httpx._transports",
        "httpcore",
        "h11",
        "certifi",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "sniffio",
        # Playwright
        "playwright",
        "playwright.async_api",
        "playwright._impl",
        "playwright._impl._api_types",
        "playwright._impl._connection",
        "playwright._impl._driver",
        "greenlet",
        "pyee",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="console-error-scanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="console-error-scanner",
)
