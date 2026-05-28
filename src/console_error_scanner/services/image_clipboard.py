"""Image-Clipboard-Helfer.

Kopiert PNG-Bytes in die OS-Zwischenablage:

- Windows: ``pywin32`` (CF_DIB). Bei Bedarf wird ``pywin32`` lazy importiert -
  fehlt das Paket, fliegt eine ``RuntimeError`` mit Installations-Hinweis.
- macOS:   ``osascript`` via temp PNG-Datei.
- Linux:   ``xclip`` oder ``wl-copy`` via temp PNG-Datei.

Wird beim Rechtsklick auf das Preview-Panel aufgerufen — die App fangt
Exceptions ab und zeigt eine notify-Toast.
"""

from __future__ import annotations

import io
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


def copy_png_to_clipboard(png_bytes: bytes) -> None:
    """Kopiert PNG-Bytes ins OS-Clipboard.

    Args:
        png_bytes: Roh-PNG-Daten.

    Raises:
        RuntimeError: Wenn das OS keine unterstuetzte Methode hat oder
            die noetigen Tools fehlen.
    """
    system = platform.system()
    if system == "Windows":
        _copy_windows(png_bytes)
    elif system == "Darwin":
        _copy_macos(png_bytes)
    else:
        _copy_linux(png_bytes)


def _copy_windows(png_bytes: bytes) -> None:
    """Windows: CF_DIB via pywin32."""
    try:
        import win32clipboard  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pywin32 fehlt. Installiere es per `pip install pywin32`.") from exc

    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow fehlt.") from exc

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = io.BytesIO()
    img.save(out, "BMP")
    # CF_DIB erwartet die BMP-Daten OHNE den 14-Byte BITMAPFILEHEADER.
    dib = out.getvalue()[14:]
    out.close()

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
    finally:
        win32clipboard.CloseClipboard()


def _copy_macos(png_bytes: bytes) -> None:
    """macOS: temp PNG + osascript (set the clipboard to ...)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes)
        path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)',
            ],
            check=True,
            capture_output=True,
        )
    finally:
        path.unlink(missing_ok=True)


def _copy_linux(png_bytes: bytes) -> None:
    """Linux: wl-copy (Wayland) bevorzugt, sonst xclip."""
    if shutil.which("wl-copy"):
        subprocess.run(["wl-copy", "--type", "image/png"], input=png_bytes, check=True)
        return
    if shutil.which("xclip"):
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png"],
            input=png_bytes,
            check=True,
        )
        return
    raise RuntimeError(
        "Weder `wl-copy` (Wayland) noch `xclip` (X11) gefunden. "
        "Installiere eines der beiden, um Bilder ins Clipboard zu kopieren."
    )
