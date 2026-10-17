"""Settings: device lock, export / import (merge), exchange rates."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.toolbar import MDTopAppBar

from .. import APP_NAME, __version__, services
from ..core.transfer import export_json, import_json
from .widgets import GREY, Field, Row, choose, form, label, toast

LOCK_KEY = "lock_enabled"


class SettingsScreen(MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="settings", **kwargs)
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(
            title="Settings", elevation=2,
            left_action_items=[["arrow-left", lambda _w: self.app.go_home()]]))
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        scroll = ScrollView()
        scroll.add_widget(self.body)
        root.add_widget(scroll)
        self.add_widget(root)
        self._build()

    @property
    def app(self) -> Any:  # type: ignore[override]
        return MDApp.get_running_app()

    def _item(self, title: str, hint: str, on_tap: Optional[Callable[[], None]],
              trailing: Any = None) -> None:
        row = Row(on_tap=on_tap, height=68)
        row.add_widget(label(f"[b]{title}[/b]\n[size=12sp][color={GREY}]{hint}[/color][/size]"))
        if trailing is not None:
            row.add_widget(trailing)
        self.body.add_widget(row)

    def _build(self) -> None:
        self.switch = MDSwitch(pos_hint={"center_y": 0.5}, size_hint_x=None, width=dp(64))
        self.switch.bind(active=lambda _w, on: self.set_lock(on))
        self._item("Require device lock", "Ask for your phone PIN / pattern / fingerprint "
                   "when the app opens", None, self.switch)
        self._item("Export all data", "Save a backup file you can import on another phone",
                   self.export_data)
        self._item("Import and merge data", "Add data from an export file; newer changes win, "
                   "nothing is deleted", self.import_data)
        self._item("Exchange rates", "Approximate offline INR rates", self.edit_rates)
        self._item(APP_NAME, f"Version {__version__}", None)

    def on_pre_enter(self, *_args: Any) -> None:
        self.switch.active = self.app.repo.get_meta(LOCK_KEY) == "1"

    # -------------------------------------------------------------- actions
    def set_lock(self, on: bool) -> None:
        if (self.app.repo.get_meta(LOCK_KEY) == "1") == on:
            return
        if on and not services.device_is_secure() and services.IS_ANDROID:
            toast("Set a screen lock in your phone settings first")
            self.switch.active = False
            return
        self.app.repo.set_meta(LOCK_KEY, "1" if on else "0")

    def export_data(self) -> None:
        name = f"my-shopping-lists-{datetime.now():%Y%m%d-%H%M}.json"
        services.save_text_file(name, export_json(self.app.repo), toast)

    def import_data(self) -> None:
        if services.HAS_FILE_PICKER:
            services.pick_text_file(self._imported)
            return

        def from_path(v: dict) -> None:
            try:
                text = services.read_path(v["path"].strip())
            except OSError as exc:
                raise ValueError(f"Could not read file: {exc}") from exc
            self._imported(text, "")

        form("Import file path", [Field("path", "Path to export file")], from_path, "Import")

    def _imported(self, text: Optional[str], error: str) -> None:
        if text is None:
            if error:
                toast(error)
            return
        try:
            report = import_json(self.app.repo, text)
        except ValueError as exc:
            toast(str(exc))
            return
        toast(f"Imported: {report}")

    def edit_rates(self) -> None:
        rates = self.app.rates.all()
        options = [(f"{code}  ·  ₹{rate:g}", code) for code, rate in sorted(rates.items())
                   if code != "INR"]
        options.append(("+ Add / edit another currency...", None))

        def picked(code: Optional[str]) -> None:
            fields = [Field("code", "Currency code", value=code or "")]
            fields.append(Field("rate", "INR per 1 unit", "number",
                                rates.get(code, "") if code else ""))

            def save(v: dict) -> None:
                self.app.rates.set_rate(v["code"], v["rate"])
                toast("Rate saved")

            form("Exchange rate", fields, save)

        choose("Exchange rates", options, picked)
