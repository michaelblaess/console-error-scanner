"""Settings-Dialog fuer den Console Error Scanner.

Erbt vom standardisierten ``BaseSettingsScreen`` (textual-widgets): die Basis
liefert Look, Sprach-Tab und Save/Cancel; diese Klasse ergaenzt nur den
Scanner-Tab mit den App-spezifischen Optionen.
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Checkbox, Input, Label, Select, Static, TabPane
from textual_slider import Slider
from textual_widgets import BaseSettingsScreen

from ..i18n import t
from ..models.history import History
from ..models.settings import SETTINGS_FILE


class ScannerSettingsScreen(BaseSettingsScreen):
    """Settings: Sprache (von der Basis) + Scanner-Optionen."""

    DEFAULT_CSS = """
    /* Label-Spalte: Label + (?)-Icon nebeneinander, gemeinsame feste Breite,
       damit alle Eingabefelder bündig untereinander stehen. Breite muss das
       laengste Label ("Groessen-Warnung (MB)" / "Size warning (MB)") plus das
       (?)-Icon fassen, sonst wird das Icon abgeschnitten. */
    ScannerSettingsScreen .label-with-icon {
        width: 26;
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
    ScannerSettingsScreen .rate-value {
        padding: 0 1;
    }
    ScannerSettingsScreen .rate-value.off {
        color: $text-disabled;
    }
    ScannerSettingsScreen #set-rate {
        width: 1fr;
        margin: 0 1;
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
                yield from self._label_with_icon(t("settings.robots_label"), t("settings.robots_tip"))
                yield Checkbox(
                    t("settings.robots_checkbox"),
                    value=bool(self._settings.get("respect_robots", True)),
                    id="set-robots",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.concurrency_label"), t("settings.concurrency_tip"))
                yield Input(
                    value=str(self._settings.get("concurrency", 8)),
                    type="integer",
                    id="set-concurrency",
                )
            rate_on = bool(self._settings.get("rate_limit_enabled", True))
            rate_value = self._clamp(self._settings.get("rate_per_minute", 60), 60, 10, 240)
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.rate_label"), t("settings.rate_tip"))
                yield Checkbox(
                    t("settings.rate_checkbox"),
                    value=rate_on,
                    id="set-rate-on",
                )
            yield Static(
                self._rate_label(rate_value),
                id="rate-value",
                classes="rate-value" if rate_on else "rate-value off",
            )
            yield Slider(min=10, max=240, step=10, value=rate_value, id="set-rate", disabled=not rate_on)
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.timeout_label"), t("settings.timeout_tip"))
                yield Input(
                    value=str(self._settings.get("timeout", 60)),
                    type="integer",
                    id="set-timeout",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.size_warn_label"), t("settings.size_warn_tip"))
                yield Input(
                    value=str(self._settings.get("size_warn_mb", 10)),
                    type="integer",
                    id="set-size-warn",
                )
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.score_weight_label"), t("settings.score_weight_tip"))
                yield Input(
                    value=str(self._settings.get("score_error_weight", 60)),
                    type="integer",
                    id="set-score-weight",
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

        with TabPane(t("settings.tab_network"), id="settings-tab-network"), VerticalScroll():
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.proxy_url_label"), t("settings.proxy_url_tip"))
                yield Input(
                    value=str(self._settings.get("proxy_url", "")),
                    placeholder="http://proxy.example.com:8080",
                    id="set-proxy-url",
                )
            yield Static(t("settings.proxy_hint"), classes="settings-hint")

        with TabPane(t("settings.tab_export"), id="settings-tab-export"), VerticalScroll():
            with Horizontal(classes="settings-row"):
                yield from self._label_with_icon(t("settings.jira_format_label"), t("settings.jira_format_tip"))
                yield Select(
                    [
                        (t("settings.jira_format_markdown"), "markdown"),
                        (t("settings.jira_format_wiki"), "wiki"),
                    ],
                    value=str(self._settings.get("jira_format", "markdown")),
                    allow_blank=False,
                    id="set-jira-format",
                )
            yield Static(t("settings.jira_format_hint"), classes="settings-hint")

    @staticmethod
    def _clamp(value: object, default: int, lo: int, hi: int) -> int:
        """Begrenzt einen gespeicherten Wert auf den Bereich des Reglers."""
        try:
            return max(lo, min(hi, int(str(value))))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _rate_label(per_minute: int) -> str:
        """Uebersetzt die Reglerstellung in Klartext (Zahl + Einordnung)."""
        if per_minute <= 30:
            step = t("settings.rate_step_gentle")
        elif per_minute <= 90:
            step = t("settings.rate_step_careful")
        elif per_minute <= 150:
            step = t("settings.rate_step_brisk")
        else:
            step = t("settings.rate_step_reckless")
        return t("settings.rate_value", count=per_minute, step=step)

    @on(Slider.Changed, "#set-rate")
    def _on_rate_changed(self, event: Slider.Changed) -> None:
        """Haelt die Beschriftung ueber dem Regler am aktuellen Wert."""
        self.query_one("#rate-value", Static).update(self._rate_label(int(event.slider.value)))

    @on(Checkbox.Changed, "#set-rate-on")
    def _on_rate_toggled(self, event: Checkbox.Changed) -> None:
        """Sperrt den Regler, solange nicht gedrosselt wird."""
        enabled = bool(event.value)
        self.query_one("#set-rate", Slider).disabled = not enabled
        self.query_one("#rate-value", Static).set_class(not enabled, "off")

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
        settings["respect_robots"] = self.query_one("#set-robots", Checkbox).value
        settings["concurrency"] = self._int("#set-concurrency", 8)
        settings["rate_limit_enabled"] = self.query_one("#set-rate-on", Checkbox).value
        settings["rate_per_minute"] = int(self.query_one("#set-rate", Slider).value)
        settings["timeout"] = self._int("#set-timeout", 60, minimum=5)
        settings["size_warn_mb"] = self._int("#set-size-warn", 10, minimum=0)
        settings["score_error_weight"] = min(100, self._int("#set-score-weight", 60, minimum=0))
        level_select = self.query_one("#set-console-level", Select)
        level_value = level_select.value
        settings["console_level"] = str(level_value) if level_value is not Select.BLANK else "warn"
        settings["show_preview"] = self.query_one("#set-preview", Checkbox).value
        settings["no_headless"] = self.query_one("#set-no-headless", Checkbox).value
        settings["whitelist_path"] = self.query_one("#set-whitelist", Input).value.strip()
        settings["user_agent"] = self.query_one("#set-user-agent", Input).value.strip()
        settings["cookies"] = self.query_one("#set-cookies", Input).value.strip()
        settings["proxy_url"] = self.query_one("#set-proxy-url", Input).value.strip()
        jira_select = self.query_one("#set-jira-format", Select)
        jira_value = jira_select.value
        settings["jira_format"] = str(jira_value) if jira_value is not Select.BLANK else "markdown"

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
