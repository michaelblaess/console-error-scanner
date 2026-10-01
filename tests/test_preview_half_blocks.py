"""Tests fuer die Half-Block-Vorschau (Fallback ohne Grafikprotokoll)."""

from __future__ import annotations

import io

from PIL import Image
from rich.console import Console

from console_error_scanner.widgets.preview_panel import _render_half_blocks


def _png(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height))
    for x in range(width):
        for y in range(height):
            img.putpixel((x, y), (61 + x, 78 + y, 180))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def test_half_blocks_tragen_beide_farben() -> None:
    lines = _render_half_blocks(_png(8, 8), max_width=8, max_height=4)
    assert lines
    style = lines[0].spans[0].style
    assert not isinstance(style, str)
    assert style.color is not None
    assert style.bgcolor is not None


def test_half_blocks_lassen_sich_rendern() -> None:
    # Vor dem Fix stand hier ein Style-String mit Leerzeichen in rgb(...).
    # Rich verwarf ihn still, Textual brach mit MissingStyle ab.
    lines = _render_half_blocks(_png(8, 8), max_width=8, max_height=4)
    console = Console(file=io.StringIO(), force_terminal=True, color_system="truecolor")
    for line in lines:
        console.print(line)
    assert "38;2;" in console.file.getvalue()  # type: ignore[attr-defined]
