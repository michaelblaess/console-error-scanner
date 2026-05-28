"""Whitelist-Viewer: zeigt die aktuell geladenen Patterns in einem Modal."""

from __future__ import annotations

import contextlib
from fnmatch import fnmatch

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ..i18n import t
from ..models.scan_result import ScanResult
from ..models.whitelist import Whitelist


class WhitelistScreen(ModalScreen[None]):
    """Modal-Dialog mit den geladenen Whitelist-Patterns und deren Treffern."""

    DEFAULT_CSS = """
    WhitelistScreen {
        align: center middle;
    }

    WhitelistScreen > Vertical {
        width: 90%;
        max-width: 110;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    WhitelistScreen #wl-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $accent;
        color: auto;
        margin-bottom: 1;
    }

    WhitelistScreen #wl-meta {
        height: auto;
        padding: 0;
        margin-bottom: 1;
        color: $text-muted;
    }

    WhitelistScreen #wl-empty {
        height: auto;
        padding: 2 4;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }

    WhitelistScreen #wl-table {
        height: auto;
        max-height: 25;
    }

    WhitelistScreen #wl-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    WhitelistScreen #wl-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q,Q", "close", "Close", key_display="q"),
        Binding("w,W", "close", "Close", show=False),
    ]

    def __init__(
        self,
        whitelist: Whitelist | None,
        results: list[ScanResult] | None = None,
        **kwargs,
    ) -> None:
        """Erstellt den Whitelist-Viewer.

        Args:
            whitelist: Geladene Whitelist oder None.
            results: Aktuelle Scan-Ergebnisse (fuer Treffer-Zaehlung).
        """
        super().__init__(**kwargs)
        self._whitelist = whitelist
        self._results = results or []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(t("whitelist.title"), id="wl-title")

            if self._whitelist is None or not self._whitelist.patterns:
                yield Static(t("whitelist.empty"), id="wl-empty")
            else:
                meta = (
                    f"{t('whitelist.path', path=self._whitelist.path)}\n"
                    f"{t('whitelist.active', count=len(self._whitelist.patterns))}"
                )
                yield Static(meta, id="wl-meta")
                table: DataTable[str] = DataTable(id="wl-table", cursor_type="row", zebra_stripes=True)
                table.add_columns(
                    t("whitelist.col_number"),
                    t("whitelist.col_pattern"),
                    t("whitelist.col_hits"),
                )
                hit_counts = self._count_hits()
                for idx, pattern in enumerate(self._whitelist.patterns, start=1):
                    hits = hit_counts.get(pattern, 0)
                    table.add_row(str(idx), pattern, str(hits), key=str(idx))
                yield table

            with Horizontal(id="wl-buttons"):
                yield Button(t("binding.close"), variant="primary", id="wl-close")

    @on(Button.Pressed, "#wl-close")
    def _on_close_button(self) -> None:
        self.dismiss(None)

    def on_mount(self) -> None:
        if self._whitelist is not None and self._whitelist.patterns:
            with contextlib.suppress(Exception):
                self.query_one("#wl-table", DataTable).focus()

    def _count_hits(self) -> dict[str, int]:
        """Zaehlt pro Pattern, wie viele Fehlermeldungen darauf gematcht haben."""
        counts: dict[str, int] = {}
        if self._whitelist is None:
            return counts
        patterns_lower = [p.lower() for p in self._whitelist.patterns]
        for result in self._results:
            for error in result.errors:
                if not error.whitelisted:
                    continue
                msg = (error.message or "").lower()
                for original, lowered in zip(self._whitelist.patterns, patterns_lower, strict=True):
                    if fnmatch(msg, lowered):
                        counts[original] = counts.get(original, 0) + 1
                        break
        return counts

    def action_close(self) -> None:
        self.dismiss(None)
