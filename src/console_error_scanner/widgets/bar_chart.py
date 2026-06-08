"""Einfacher horizontaler Balken-Chart als Rich-Text (Terminal-Bars).

Wird vom Diaet-Ratgeber (groesste Ressourcen einer Seite) und von der
Scan-Zusammenfassung (groesste Seiten/Ressourcen) genutzt.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text

_BLOCK = "█"
_EMPTY = "░"


def render_bars(
    rows: Sequence[tuple[int, str, str | Text]],
    max_bar: int = 22,
    bar_style: str = "cyan",
) -> Text:
    """Rendert Zeilen als horizontale Balken.

    Args:
        rows:
            Liste aus ``(wert, wert_label, text)`` - z.B.
            ``(2517000, "2,4 MB", "jpeg  bild.jpg")``. Die Balkenlaenge ist
            relativ zum groessten Wert. Ist ``text`` ein ``Text`` (statt eines
            ``str``), wird es unveraendert uebernommen - so bleiben z.B.
            Klick-Aktionen (``@click``-Meta) fuer Hover-Links erhalten.
        max_bar:
            Maximale Balkenbreite in Zellen.
        bar_style:
            Rich-Style fuer die gefuellten Balken.

    Returns:
        Ein mehrzeiliges ``Text``-Objekt.
    """
    out = Text()
    if not rows:
        return out
    top = max((v for v, _, _ in rows), default=1) or 1
    value_width = max((len(vl) for _, vl, _ in rows), default=0)
    for i, (value, value_label, text) in enumerate(rows):
        filled = int(round(max_bar * value / top)) if top else 0
        if value > 0:
            filled = max(1, filled)
        filled = min(filled, max_bar)
        if i:
            out.append("\n")
        out.append(_BLOCK * filled, style=bar_style)
        out.append(_EMPTY * (max_bar - filled), style="dim")
        out.append("  ")
        out.append(value_label.rjust(value_width), style="bold")
        out.append("  ")
        if isinstance(text, Text):
            out.append_text(text)
        else:
            out.append(text, style="dim")
    return out
