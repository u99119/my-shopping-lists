"""Push Options screen: pick when to add the chosen phrase to B's calendar."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDRaisedButton
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar
from kivy.utils import escape_markup

from ..cal import config as cfgmod, event_service as svc, timing
from .widgets import GREY, Row, label, toast, toast_action

FIXED_HOURS = (10, 15, 18, 21)  # 10 AM, 3 PM, 6 PM, 9 PM


class CalPushOptionsScreen(MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="cal_push", **kwargs)
        self._phrase_idx: Optional[int] = None
        self._x_hours: int = cfgmod.DEFAULT_X_HOURS
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(
            title="Push Options", elevation=2,
            left_action_items=[["arrow-left", lambda _w: self.app.open_screen("mycal")]]))
        self.header = MDBoxLayout(orientation="vertical", size_hint_y=None,
                                  adaptive_height=True, padding=(dp(16), dp(8), dp(16), dp(8)))
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        scroll = ScrollView()
        inner = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        inner.add_widget(self.header)
        inner.add_widget(self.body)
        scroll.add_widget(inner)
        root.add_widget(scroll)
        self.add_widget(root)

    @property
    def app(self) -> Any:
        return MDApp.get_running_app()

    def load(self, phrase_idx: int) -> None:
        self._phrase_idx = phrase_idx
        cfg = cfgmod.load()
        self._x_hours = cfg.last_x_hours
        self._rebuild()

    def _rebuild(self) -> None:
        self.header.clear_widgets()
        self.body.clear_widgets()
        cfg = cfgmod.load()
        if self._phrase_idx is None or not (0 <= self._phrase_idx < len(cfg.phrases)):
            self.header.add_widget(label("[i]No phrase selected.[/i]"))
            return
        p = cfg.phrases[self._phrase_idx]
        self.header.add_widget(label(f"[b]{escape_markup(p.text)}[/b]"))
        self.header.add_widget(label(
            f"[size=12sp][color={GREY}]default "
            f"{timing.format_hhmm(p.default_hh, p.default_mm)}[/color][/size]"))

        self._add_option("Push NOW (+5 min)", "now")
        self._add_option(f"Push at default ({timing.format_hhmm(p.default_hh, p.default_mm)})",
                         "default")
        self._add_option("Push at next :30", "next_half")
        self._add_option("Push at next :00", "next_oclock")
        self.body.add_widget(self._x_hours_row())
        for hh in FIXED_HOURS:
            self._add_option(self._fixed_label(hh), "fixed", fixed_hh=hh)

    def _add_option(self, text: str, option: str, **extra: Any) -> None:
        when = self._preview(option, **extra)
        preview = when.strftime("%a %H:%M") if when else "—"
        row = Row(on_tap=lambda o=option, e=extra: self._do(o, **e), height=56)
        row.add_widget(label(f"{escape_markup(text)}\n"
                             f"[size=11sp][color={GREY}]{preview}[/color][/size]"))
        self.body.add_widget(row)

    def _x_hours_row(self) -> Row:
        row = Row(height=56, padding=(dp(12), 0, dp(8), 0))
        preview = self._preview("x_hours", x_hours=self._x_hours)
        preview_str = preview.strftime("%a %H:%M") if preview else "—"
        txt = label(f"Push +{self._x_hours}h\n"
                    f"[size=11sp][color={GREY}]{preview_str}[/color][/size]")
        minus = MDIconButton(icon="minus", pos_hint={"center_y": 0.5},
                             on_release=lambda *_: self._bump_x(-1))
        plus = MDIconButton(icon="plus", pos_hint={"center_y": 0.5},
                            on_release=lambda *_: self._bump_x(+1))
        go = MDRaisedButton(text="Push", pos_hint={"center_y": 0.5},
                            on_release=lambda *_: self._do("x_hours", x_hours=self._x_hours))
        row.add_widget(txt)
        row.add_widget(minus)
        row.add_widget(plus)
        row.add_widget(go)
        return row

    def _bump_x(self, delta: int) -> None:
        self._x_hours = max(1, min(24, self._x_hours + delta))
        self._rebuild()

    def _preview(self, option: str, **extra: Any) -> Optional[datetime]:
        cfg = cfgmod.load()
        if self._phrase_idx is None:
            return None
        p = cfg.phrases[self._phrase_idx]
        try:
            return svc.resolve_when(option, phrase=p, **extra)
        except Exception:
            return None

    def _fixed_label(self, hh: int) -> str:
        if hh == 0:
            return "Push at 12 AM"
        if hh < 12:
            return f"Push at {hh} AM"
        if hh == 12:
            return "Push at 12 PM"
        return f"Push at {hh - 12} PM"

    def _do(self, option: str, **extra: Any) -> None:
        if self._phrase_idx is None:
            toast("No phrase selected.")
            return
        try:
            res = svc.push(phrase_index=self._phrase_idx, text=None, option=option, **extra)
        except svc.ConfigError:
            toast("Open Settings and set the calendar first.")
            self.app.open_screen("cal_settings")
            return
        except Exception as exc:  # noqa: BLE001
            toast(f"Push failed: {exc}")
            return
        when = res.when.strftime("%a %H:%M")
        toast_action(f"Added '{res.text}' at {when}", "Undo",
                     lambda eid=res.event_id: self._undo(eid))
        self.app.open_screen("mycal")

    def _undo(self, event_id: str) -> None:
        try:
            svc.undo(event_id)
            toast("Undone.")
        except Exception as exc:  # noqa: BLE001
            toast(f"Undo failed: {exc}")
