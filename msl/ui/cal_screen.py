"""MY CAL screen: list of up to 12 phrases with NOW / default quick-push icons."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar
from kivy.utils import escape_markup

from ..cal import config as cfgmod, event_service as svc, timing
from .widgets import (GREY, Row, Field, compact_icon, confirm, form, label, menu, toast,
                      toast_action)

ROW_TRUNCATE = 30  # first 30 chars shown on MY CAL (per spec)


def _start_hhmm(start: dict) -> str:
    """'HH:MM' in local time for timed events, 'all day' for date-only events."""
    dt = start.get("dateTime")
    if not dt:
        return "all day" if start.get("date") else ""
    try:
        return datetime.fromisoformat(dt).astimezone().strftime("%H:%M")
    except ValueError:
        return dt


class CalScreen(MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="mycal", **kwargs)
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(
            title="MY CAL", elevation=2,
            left_action_items=[["arrow-left", lambda _w: self.app.go_home()]],
            right_action_items=[["cog", lambda _w: self.app.open_screen("cal_settings")]]))
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        scroll = ScrollView()
        scroll.add_widget(self.body)
        root.add_widget(scroll)
        bottom = Row(height=48, padding=(dp(12), 0, dp(12), 0),
                     on_tap=lambda: self._show_today())
        bottom.add_widget(label(f"[color={GREY}]Tap to see B's calendar today[/color]"))
        bottom.add_widget(MDIconButton(icon="calendar-today", pos_hint={"center_y": 0.5},
                                       on_release=lambda _w: self._show_today()))
        root.add_widget(bottom)
        self.add_widget(root)

    @property
    def app(self) -> Any:
        return MDApp.get_running_app()

    def on_pre_enter(self, *_args: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.body.clear_widgets()
        cfg = cfgmod.load()
        for i, p in enumerate(cfg.phrases):
            self.body.add_widget(self._phrase_row(i, p))
        if len(cfg.phrases) < cfgmod.MAX_PHRASES:
            self.body.add_widget(self._add_row())

    def _phrase_row(self, idx: int, p: cfgmod.Phrase) -> Row:
        text = p.text if len(p.text) <= ROW_TRUNCATE else p.text[:ROW_TRUNCATE] + "…"
        row = Row(on_tap=lambda i=idx: self._open_push_options(i), height=56,
                  on_long_tap=lambda i=idx, ph=p: self._edit_phrase(i, ph))
        row.add_widget(label(f"[b]{idx + 1:02d}[/b]  {escape_markup(text)}\n"
                             f"[size=11sp][color={GREY}]default "
                             f"{timing.format_hhmm(p.default_hh, p.default_mm)}[/color][/size]"))
        icons = MDBoxLayout(orientation="horizontal", adaptive_width=True, spacing=0)
        icons.add_widget(compact_icon("flash", lambda _w, i=idx: self._quick_push(i, "now")))
        icons.add_widget(compact_icon("clock-outline",
                                      lambda _w, i=idx: self._quick_push(i, "default")))
        icons.add_widget(compact_icon("dots-vertical",
                                      lambda w, i=idx, ph=p: self._row_menu(w, i, ph)))
        row.add_widget(icons)
        return row

    def _row_menu(self, caller: Any, idx: int, p: cfgmod.Phrase) -> None:
        menu(caller, [
            ("Edit", lambda: self._edit_phrase(idx, p)),
            ("Delete", lambda: confirm(
                "Delete phrase", f"Delete '{p.text}'?",
                lambda: self._delete_phrase(idx))),
        ])

    def _delete_phrase(self, idx: int) -> None:
        cfg = cfgmod.load()
        try:
            cfgmod.remove_phrase(cfg, idx)
            cfgmod.save(cfg)
        except IndexError as exc:
            toast(str(exc))
            return
        self.refresh()

    def _add_row(self) -> Row:
        row = Row(on_tap=self._add_phrase, height=48)
        row.add_widget(label(f"[color={GREY}]+ Add phrase[/color]"))
        return row

    # ------------------------------------------------------------ interactions
    def _quick_push(self, idx: int, option: str) -> None:
        toast("Pushing…")
        svc.push_async(phrase_index=idx, text=None, option=option,
                       on_done=self._after_push)

    def _after_push(self, res: Any, exc: Any) -> None:
        if isinstance(exc, svc.ConfigError):
            toast("Open Settings and set the calendar first.")
            self.app.open_screen("cal_settings")
            return
        if exc is not None:
            toast(f"Push failed: {exc}")
            return
        when = res.when.strftime("%a %H:%M")
        toast_action(f"Added '{res.text}' at {when}", "Undo",
                     lambda eid=res.event_id: self._undo(eid))

    def _undo(self, event_id: str) -> None:
        svc.undo_async(event_id, lambda _r, exc: (
            toast("Undone.") if exc is None else toast(f"Undo failed: {exc}")))

    def _open_push_options(self, idx: int) -> None:
        screen = self.app.manager.get_screen("cal_push")
        screen.load(idx)
        self.app.open_screen("cal_push")

    def _add_phrase(self) -> None:
        form("Add phrase",
             [Field("text", "Phrase (max 30 chars shown)", suggest=True),
              Field("at", "Default time", kind="time", value="09:00")],
             lambda v: self._submit_add(v))

    def _submit_add(self, v: dict) -> None:
        try:
            hh, mm = timing.parse_hhmm(v["at"])
            cfg = cfgmod.load()
            cfgmod.add_phrase(cfg, v["text"], hh, mm)
            cfgmod.save(cfg)
        except (ValueError, IndexError) as exc:
            raise ValueError(str(exc))
        self.refresh()

    def _edit_phrase(self, idx: int, p: cfgmod.Phrase) -> None:
        form("Edit phrase",
             [Field("text", "Phrase", value=p.text, suggest=True),
              Field("at", "Default time", kind="time",
                    value=timing.format_hhmm(p.default_hh, p.default_mm))],
             lambda v: self._submit_edit(idx, v))

    def _submit_edit(self, idx: int, v: dict) -> None:
        try:
            hh, mm = timing.parse_hhmm(v["at"])
            cfg = cfgmod.load()
            cfgmod.update_phrase(cfg, idx, text=v["text"], hh=hh, mm=mm)
            cfgmod.save(cfg)
        except (ValueError, IndexError) as exc:
            raise ValueError(str(exc))
        self.refresh()

    def _show_today(self) -> None:
        toast("Loading…")
        svc.today_events_async(self._after_today)

    def _after_today(self, items: Any, exc: Any) -> None:
        if isinstance(exc, svc.ConfigError):
            toast("Set the calendar in Settings first.")
            return
        if exc is not None:
            toast(f"Could not fetch: {exc}")
            return
        if not items:
            toast("(no events on B's calendar today)")
            return
        lines = []
        for ev in items[:10]:
            lines.append(f"{_start_hhmm(ev.get('start', {}))}  {ev.get('summary', '')}")
        confirm("B's calendar today", "\n".join(lines), lambda: None, yes_text="OK")
