"""Settings-Dialog fuer den Console Error Scanner.

Erbt vom standardisierten ``BaseSettingsScreen`` (textual-widgets): die Basis
liefert Look, Sprach-Tab und Save/Cancel; diese Klasse ergaenzt nur den
Scanner-Tab mit den App-spezifischen Optionen.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Checkbox, Input, Label, Select, Static, TabPane
from textual_widgets import BaseSettingsScreen

from ..i18n import t
from ..models.history import History
from ..models.settings import SETTINGS_FILE


class ScannerSettingsScreen(BaseSettingsScreen):
    """Settings: Sprache (von der Basis) + Scanner-Optionen."""

    DEFAULT_CSS = """
    /* Label-Spalte: Label + (?)-Icon nebeneinander, gemeinsame feste Breite,
       damit alle Eingabefelder bündig untereinander stehen. */
    ScannerSettingsScreen .label-with-icon {
        width: 22;
        height: 1;
    }
    ScannerSettingsScreen .label-with-icon Label {
        width: auto;
        padding: 0 1 0 1;
    }
    ScannerSettingsScreen .info-icon {
        width: auto;
        height: 1;
        color: cyan;
        text-style: bold;
        padding: 0 1 0 0;
    }
    ScannerSettingsScreen .info-icon:hover {
        color: white;
        background: cyan 30%;
    }
    """

    def app_tabs(self) -> ComposeResult:
        """Scanner-Tab: Consent, Scroll, Concurrency, Timeout, Whitelist, …"""
        with TabPane(t("settings.tab_scanner"), id="settings-tab-scanner"), VerticalScroll():
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.consent_label"), t("settings.consent_tip"))
                yield Checkbox(
                    t("settings.consent_checkbox"),
                    value=bool(self._settings.get("accept_consent", True)),
                    id="set-consent",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.scroll_label"), t("settings.scroll_tip"))
                yield Checkbox(
                    t("settings.scroll_checkbox"),
                    value=bool(self._settings.get("trigger_lazy_load", True)),
                    id="set-scroll",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.concurrency_label"), t("settings.concurrency_tip"))
                yield Input(
                    value=str(self._settings.get("concurrency", 8)),
                    type="integer",
                    id="set-concurrency",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.timeout_label"), t("settings.timeout_tip"))
                yield Input(
                    value=str(self._settings.get("timeout", 60)),
                    type="integer",
                    id="set-timeout",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.console_level_label"), t("settings.console_level_tip"))
                yield Select(
                    [("error", "error"), ("warn", "warn"), ("all", "all")],
                    value=str(self._settings.get("console_level", "warn")),
                    allow_blank=False,
                    id="set-console-level",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.preview_label"), t("settings.preview_tip"))
                yield Checkbox(
                    t("settings.preview_checkbox"),
                    value=bool(self._settings.get("show_preview", False)),
                    id="set-preview",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.headless_label"), t("settings.headless_tip"))
                yield Checkbox(
                    t("settings.headless_checkbox"),
                    value=bool(self._settings.get("no_headless", False)),
                    id="set-no-headless",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.whitelist_label"), t("settings.whitelist_tip"))
                yield Input(
                    value=str(self._settings.get("whitelist_path", "")),
                    placeholder=t("settings.whitelist_placeholder"),
                    id="set-whitelist",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.user_agent_label"), t("settings.user_agent_tip"))
                yield Input(
                    value=str(self._settings.get("user_agent", "")),
                    placeholder=t("settings.user_agent_placeholder"),
                    id="set-user-agent",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.cookies_label"), t("settings.cookies_tip"))
                yield Input(
                    value=str(self._settings.get("cookies", "")),
                    placeholder=t("settings.cookies_placeholder"),
                    id="set-cookies",
                )
            yield Static(t("settings.app_hint"), classes="settings-hint")

    def _label_with_icon(self, label_text: str, tip: str) -> ComposeResult:
        """Erzeugt Label + (?)-Hover-Tooltip-Icon in der Label-Spalte."""
        with Horizontal(classes="label-with-icon"):
            yield Label(label_text)
            icon = Static(t("settings.info_icon"), classes="info-icon")
            icon.tooltip = tip
            yield icon

    def collect_app_settings(self, settings: dict[str, object]) -> None:
        """Schreibt die Scanner-Optionen aus den Widgets ins Ergebnis-Dict."""
        settings["accept_consent"] = self.query_one("#set-consent", Checkbox).value
        settings["trigger_lazy_load"] = self.query_one("#set-scroll", Checkbox).value
        settings["concurrency"] = self._int("#set-concurrency", 8)
        settings["timeout"] = self._int("#set-timeout", 60, minimum=5)
        level_select = self.query_one("#set-console-level", Select)
        level_value = level_select.value
        settings["console_level"] = str(level_value) if level_value is not Select.BLANK else "warn"
        settings["show_preview"] = self.query_one("#set-preview", Checkbox).value
        settings["no_headless"] = self.query_one("#set-no-headless", Checkbox).value
        settings["whitelist_path"] = self.query_one("#set-whitelist", Input).value.strip()
        settings["user_agent"] = self.query_one("#set-user-agent", Input).value.strip()
        settings["cookies"] = self.query_one("#set-cookies", Input).value.strip()

    def storage_paths(self) -> list[tuple[str, Path]]:
        """Liefert die Persistenz-Pfade fuer den Speicherort-Tab."""
        from ..services.preview_service import CACHE_DIR as PREVIEW_CACHE_DIR

        paths: list[tuple[str, Path]] = [
            (t("settings.storage.config"), SETTINGS_FILE),
            (t("settings.storage.history"), History.HISTORY_FILE),
        ]
        whitelist_raw = str(self._settings.get("whitelist_path", "")).strip()
        if whitelist_raw:
            paths.append((t("settings.storage.whitelist"), Path(whitelist_raw)))
        paths.append((t("settings.storage.preview_cache"), PREVIEW_CACHE_DIR))
        return paths

    def _int(self, selector: str, default: int, minimum: int = 1) -> int:
        """Liest einen Integer-Wert aus einem Input-Feld (mit Fallback)."""
        try:
            return max(minimum, int(self.query_one(selector, Input).value))
        except (ValueError, TypeError):
            return default
