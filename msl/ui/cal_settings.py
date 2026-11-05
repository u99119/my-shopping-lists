"""MY CAL settings: calendar ID, client secret path, re-auth, test connection."""

from __future__ import annotations

from typing import Any, Optional

from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar
from kivy.utils import escape_markup

from ..cal import auth, config as cfgmod, event_service as svc
from .widgets import GREY, Field, Row, form, label, toast


class CalSettingsScreen(MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="cal_settings", **kwargs)
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(
            title="MY CAL settings", elevation=2,
            left_action_items=[["arrow-left", lambda _w: self._back()]]))
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                adaptive_height=True, padding=(dp(12), dp(8), dp(12), dp(8)),
                                spacing=dp(4))
        scroll = ScrollView()
        scroll.add_widget(self.body)
        root.add_widget(scroll)
        self.add_widget(root)

    @property
    def app(self) -> Any:
        return MDApp.get_running_app()

    def _back(self) -> None:
        self.app.open_screen("mycal" if svc.is_configured() else "home")

    def on_pre_enter(self, *_args: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.body.clear_widgets()
        cfg = cfgmod.load()
        self._field_row("Calendar ID", cfg.calendar_id or "(not set)",
                        lambda: self._edit_calendar_id(cfg))
        self._field_row("client_secret.json", cfg.client_secret_path or "(not set)",
                        lambda: self._edit_client_secret(cfg))
        self._field_row("Account", cfg.account_email or "(unknown)", None)
        self._field_row("Default popup offset",
                        f"{cfg.popup_offset_min} min before",
                        lambda: self._edit_popup(cfg))
        self.body.add_widget(self._spacer())
        self.body.add_widget(MDRaisedButton(
            text="Test connection", size_hint_x=1, on_release=lambda *_: self._test()))
        self.body.add_widget(MDRaisedButton(
            text="Re-authenticate", size_hint_x=1, on_release=lambda *_: self._reauth()))
        self.body.add_widget(MDRaisedButton(
            text="Sign out (clear token)", size_hint_x=1, on_release=lambda *_: self._signout()))
        self.body.add_widget(MDRaisedButton(
            text="Manage phrases", size_hint_x=1,
            on_release=lambda *_: self.app.open_screen("mycal")))

    def _field_row(self, name: str, value: str, on_edit: Any) -> None:
        row = Row(on_tap=on_edit if on_edit else None, height=56)
        row.add_widget(label(f"[b]{escape_markup(name)}[/b]\n"
                             f"[size=12sp][color={GREY}]{escape_markup(value)}[/color][/size]"))
        self.body.add_widget(row)

    def _spacer(self) -> Row:
        return Row(height=12)

    def _edit_calendar_id(self, cfg: cfgmod.Config) -> None:
        form("Calendar ID",
             [Field("cal", "paste calendar ID (…@group.calendar.google.com)",
                    value=cfg.calendar_id or "")],
             lambda v: self._save_calendar_id(v["cal"]))

    def _save_calendar_id(self, cal_id: str) -> None:
        cal_id = cal_id.strip()
        if not cal_id:
            raise ValueError("Calendar ID cannot be empty.")
        cfg = cfgmod.load()
        cfg.calendar_id = cal_id
        cfgmod.save(cfg)
        self.refresh()

    def _edit_client_secret(self, cfg: cfgmod.Config) -> None:
        form("client_secret.json path",
             [Field("p", "absolute path", value=cfg.client_secret_path or "")],
             lambda v: self._save_client_secret(v["p"]))

    def _save_client_secret(self, p: str) -> None:
        p = p.strip()
        if not p:
            raise ValueError("Path cannot be empty.")
        cfg = cfgmod.load()
        cfg.client_secret_path = p
        cfgmod.save(cfg)
        self.refresh()

    def _edit_popup(self, cfg: cfgmod.Config) -> None:
        form("Popup offset (minutes before event)",
             [Field("m", "0..60", kind="number", value=str(cfg.popup_offset_min))],
             lambda v: self._save_popup(v["m"]))

    def _save_popup(self, s: str) -> None:
        try:
            m = int(float(s))
        except (TypeError, ValueError):
            raise ValueError("Please enter a whole number.")
        if not (0 <= m <= 60):
            raise ValueError("Enter a value between 0 and 60.")
        cfg = cfgmod.load()
        cfg.popup_offset_min = m
        cfgmod.save(cfg)
        self.refresh()

    def _test(self) -> None:
        toast("Checking…")
        svc.test_connection_async(self._after_test)

    def _after_test(self, _r: Any, exc: Optional[BaseException]) -> None:
        if isinstance(exc, svc.ConfigError):
            toast("Set calendar ID first.")
            return
        if exc is not None:
            toast(f"Test failed: {exc}")
            return
        toast("Connection OK.")

    def _reauth(self) -> None:
        print("[reauth] button tapped", flush=True)
        cfg = cfgmod.load()
        if not cfg.client_secret_path:
            toast("Set client_secret.json path first.")
            return
        print(f"[reauth] client_secret_path={cfg.client_secret_path}", flush=True)
        auth.clear_credentials()
        toast("Opening browser…")
        print("[reauth] calling ensure_credentials_async", flush=True)
        auth.ensure_credentials_async(
            cfg.client_secret_path, lambda c, e: self._after_reauth(c, e))
        print("[reauth] ensure_credentials_async returned (async)", flush=True)

    def _after_reauth(self, _creds: Any, exc: Optional[BaseException]) -> None:
        if exc is not None:
            toast(f"Auth failed: {exc}")
            return
        toast("Signed in.")

    def _signout(self) -> None:
        auth.clear_credentials()
        toast("Token cleared.")
