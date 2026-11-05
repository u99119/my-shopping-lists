"""Small reusable UI pieces: rows, menus, dialogs and forms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineAvatarListItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.textfield import MDTextField

from .. import services
from ..core.models import Priority

PRIORITY_COLOR = {1: "0d47a1", 2: "64b5f6", 3: "9e9e9e"}  # dark blue, light blue, grey
# Text colour on a priority button: white on the dark blue one, black on the two light ones.
PRIORITY_TEXT_COLOR = {1: (1, 1, 1, 1), 2: (0, 0, 0, 1), 3: (0, 0, 0, 1)}
GREY = "9e9e9e"
DARK_TEXT = (0.05, 0.05, 0.05, 1)  # near-black text for dialogs (default is a washed-out grey)

# Hierarchy bullets: very dark green hexagon > medium green square > hollow circle.
BULLET_COLOR = {"category": "0b3d0b", "subcategory": "2e7d32", "item": "2e7d32"}
BULLET_SIZE = {"category": 16, "subcategory": 12, "item": 9}


class PriorityDot(Widget):
    """Small filled circle coloured by priority (dark blue / light blue / grey).
    Drawn on the canvas because the default font has no '●' glyph on Android."""

    def __init__(self, priority: int, color: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(size_hint=(None, None), size=(dp(12), dp(20)),
                         pos_hint={"center_y": 0.5}, **kwargs)
        self.hex = color or PRIORITY_COLOR[int(priority)]
        self.bind(pos=self._draw, size=self._draw)
        self._draw()

    def _draw(self, *_a: Any) -> None:
        d = dp(10)
        self.canvas.clear()
        with self.canvas:
            Color(*get_color_from_hex(self.hex))
            Ellipse(pos=(self.center_x - d / 2, self.center_y - d / 2), size=(d, d))


class Bullet(Widget):
    """Shape marking the row level: filled hexagon (category), filled square
    (sub-category) or hollow circle (item). Drawn on the canvas, so it needs no font."""

    def __init__(self, kind: str, **kwargs: Any) -> None:
        super().__init__(size_hint=(None, None), size=(dp(20), dp(20)),
                         pos_hint={"center_y": 0.5}, **kwargs)
        self.kind = kind
        self.bind(pos=self._draw, size=self._draw)
        self._draw()

    def _draw(self, *_a: Any) -> None:
        d = dp(BULLET_SIZE[self.kind])
        x, y = self.center_x - d / 2, self.center_y - d / 2
        self.canvas.clear()
        with self.canvas:
            Color(*get_color_from_hex(BULLET_COLOR[self.kind]))
            if self.kind == "category":
                Ellipse(pos=(x, y), size=(d, d), segments=6)
            elif self.kind == "subcategory":
                Rectangle(pos=(x, y), size=(d, d))
            else:
                Line(circle=(self.center_x, self.center_y, d / 2 - dp(0.75)), width=dp(1.5))


LONG_PRESS_S = 0.5


class Row(ButtonBehavior, MDBoxLayout):
    """A fixed-height horizontal row that can be tapped (and optionally long-pressed)."""

    def __init__(self, on_tap: Optional[Callable[[], None]] = None, height: float = 56,
                 on_long_tap: Optional[Callable[[], None]] = None, **kwargs: Any) -> None:
        kwargs.setdefault("padding", (dp(12), 0, 0, 0))
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(height),
                         spacing=dp(4), **kwargs)
        self._on_tap = on_tap
        self._on_long_tap = on_long_tap
        self._long_ev: Any = None
        self._long_fired = False
        if on_long_tap:
            self.bind(on_press=self._start_long)
        if on_tap or on_long_tap:
            self.bind(on_release=self._released)

    def _start_long(self, *_a: Any) -> None:
        self._long_fired = False
        self._cancel_long()
        self._long_ev = Clock.schedule_once(self._fire_long, LONG_PRESS_S)

    def _fire_long(self, _dt: float) -> None:
        self._long_ev = None
        if self.state == "down" and self._on_long_tap:
            self._long_fired = True
            self._on_long_tap()

    def _cancel_long(self) -> None:
        if self._long_ev is not None:
            self._long_ev.cancel()
            self._long_ev = None

    def _released(self, *_a: Any) -> None:
        self._cancel_long()
        if self._long_fired:  # the long press already acted; don't also tap
            self._long_fired = False
            return
        if self._on_tap:
            self._on_tap()


def compact_icon(icon: str, on_release: Callable[[Any], None]) -> MDIconButton:
    """Icon button with a 36dp touch box instead of 48dp, for rows with several icons."""
    btn = MDIconButton(icon=icon, pos_hint={"center_y": 0.5}, on_release=on_release)
    btn._default_icon_pad = dp(12)  # read by MDIconButton.set_size (scheduled after init)
    return btn


def label(text: str, **kwargs: Any) -> MDLabel:
    kwargs.setdefault("line_height", 0.95)  # tighter spacing between the lines of a row
    return MDLabel(text=text, markup=True, valign="center", **kwargs)


def _snackbar_y() -> float:
    """Snackbars attach to the window, so lift them above the navigation bar."""
    insets = services.system_bar_insets()
    return (insets[3] if insets else 0) + dp(8)


def toast(message: str) -> None:
    MDSnackbar(MDLabel(text=message, theme_text_color="Custom",
                       text_color=(1, 1, 1, 1)), duration=2.5, y=_snackbar_y()).open()


def toast_action(message: str, action_text: str, on_action: Callable[[], None],
                 duration: float = 5.0) -> None:
    """Snackbar with a text action (e.g. Undo). Dismisses on action or timeout."""
    bar: MDSnackbar

    def _do(*_a: Any) -> None:
        bar.dismiss()
        on_action()

    bar = MDSnackbar(
        MDLabel(text=message, theme_text_color="Custom", text_color=(1, 1, 1, 1)),
        MDFlatButton(text=action_text, theme_text_color="Custom",
                     text_color=(1, 1, 1, 1), on_release=_do),
        duration=duration,
        y=_snackbar_y(),
    )
    bar.open()


def menu(caller, entries: Sequence[tuple[str, Callable[[], None]]]) -> MDDropdownMenu:
    """Open a dropdown under ``caller``; each entry is ``(text, callback)``."""
    dropdown: MDDropdownMenu

    def run(callback: Callable[[], None]) -> None:
        dropdown.dismiss()
        Clock.schedule_once(lambda _dt: callback(), 0.05)

    dropdown = MDDropdownMenu(
        caller=caller, width_mult=4,
        items=[{"viewclass": "OneLineListItem", "text": text,
                "on_release": (lambda cb=cb: run(cb))} for text, cb in entries],
    )
    dropdown.open()
    return dropdown


def _tidy(dialog: MDDialog) -> MDDialog:
    """Darker text and tighter vertical padding than the KivyMD defaults."""
    dialog.ids.container.padding = (dp(24), dp(16), dp(8), dp(4))
    dialog.ids.title.theme_text_color = "Custom"
    dialog.ids.title.text_color = DARK_TEXT
    dialog.ids.title.line_height = 0.95
    dialog.ids.text.text_color = DARK_TEXT
    dialog.ids.text.line_height = 0.95
    return dialog


def _dialog(title: str, content=None, buttons=(), pin_top: bool = False,
            **kwargs: Any) -> MDDialog:
    dialog = _tidy(MDDialog(title=title, buttons=list(buttons), **(
        {"type": "custom", "content_cls": content} if content is not None else {}), **kwargs))
    if pin_top:
        # Put the dialog just under the status bar instead of centring it, so the keyboard
        # can't cover it. ModalView re-centres itself via ``_align_center`` (looked up when the
        # dialog opens), so replace that on this instance *before* ``open()``.
        insets = services.system_bar_insets()
        gap = (insets[1] if insets else 0) + dp(8)

        def align_top(*_args: Any) -> None:
            if dialog._is_open:
                dialog.center_x = dialog._window.center[0]
                dialog.top = dialog._window.height - gap

        dialog._align_center = align_top  # type: ignore[method-assign]
    dialog.open()
    return dialog


def confirm(title: str, text: str, on_yes: Callable[[], None], yes_text: str = "Delete") -> None:
    dialog: MDDialog

    def yes(*_a: Any) -> None:
        dialog.dismiss()
        on_yes()

    dialog = _tidy(MDDialog(
        title=title, text=text,
        buttons=[MDFlatButton(text="Cancel", on_release=lambda *_: dialog.dismiss()),
                 MDRaisedButton(text=yes_text, on_release=yes)],
    ))
    dialog.open()


def choose(title: str, options: Sequence[tuple[str, Any]], on_pick: Callable[[Any], None]) -> None:
    """Dialog listing ``(label, value)`` options; calls ``on_pick(value)``."""
    dialog: MDDialog

    def pick(value: Any) -> None:
        dialog.dismiss()
        Clock.schedule_once(lambda _dt: on_pick(value), 0.05)

    dialog = _tidy(MDDialog(
        title=title, type="simple",
        # MDDialog "simple" needs items that own a ``_left_container`` (avatar list items).
        items=[OneLineAvatarListItem(text=text, on_release=(lambda _w, v=value: pick(v)))
               for text, value in options],
    ))
    dialog.open()


class PriorityPicker(MDBoxLayout):
    """Three buttons: 1 Must have, 2 Good to have, 3 Can avoid."""

    def __init__(self, value: int = 1, **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(48),
                         spacing=dp(6), **kwargs)
        self.value = int(value)
        self._buttons: dict[int, MDRaisedButton] = {}
        for p in Priority:
            btn = MDRaisedButton(text=p.label, font_size="12sp", rounded_button=True,
                                 on_release=lambda _b, p=int(p): self.select(p))
            self._buttons[int(p)] = btn
            self.add_widget(btn)
        self.select(self.value)

    def select(self, value: int) -> None:
        self.value = value
        for p, btn in self._buttons.items():
            btn.md_bg_color = get_color_from_hex(PRIORITY_COLOR[p])
            btn.theme_text_color = "Custom"
            btn.text_color = PRIORITY_TEXT_COLOR[p]
            btn.opacity = 1 if p == value else 0.4  # selected one is solid, others faded


class TimeStepper(MDBoxLayout):
    """HH:MM picker: hour −/+ in 1 h steps, minute −/+ in 5 min steps (both wrap)."""

    def __init__(self, caption: str, value: Any = "09:00", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(64), **kwargs)
        try:
            hh, mm = (int(x) for x in str(value).split(":"))
        except ValueError:
            hh, mm = 9, 0
        self.hh, self.mm = hh % 24, mm % 60
        self.add_widget(MDLabel(text=caption, font_style="Caption", size_hint_y=None,
                                height=dp(16), theme_text_color="Custom",
                                text_color=(0.25, 0.25, 0.25, 1)))
        row = MDBoxLayout(orientation="horizontal", adaptive_width=True,
                          pos_hint={"center_x": 0.5})
        self._hh_label = self._group(row, self._step_hour)
        row.add_widget(self._digits(":", width=12))
        self._mm_label = self._group(row, self._step_minute)
        self.add_widget(row)
        self._show()

    @property
    def value(self) -> str:
        return f"{self.hh:02d}:{self.mm:02d}"

    def _digits(self, text: str, width: float = 40) -> MDLabel:
        return MDLabel(text=text, halign="center", font_size="20sp", size_hint_x=None,
                       width=dp(width), theme_text_color="Custom", text_color=DARK_TEXT)

    def _group(self, row: MDBoxLayout, step: Callable[[int], None]) -> MDLabel:
        digits = self._digits("")
        row.add_widget(compact_icon("minus", lambda _w: step(-1)))
        row.add_widget(digits)
        row.add_widget(compact_icon("plus", lambda _w: step(1)))
        return digits

    def _step_hour(self, d: int) -> None:
        self.hh = (self.hh + d) % 24
        self._show()

    def _step_minute(self, d: int) -> None:
        # Snap to the 5-minute grid: 07 → + 10, − 05.
        self.mm = (self.mm // 5 * 5 + 5) % 60 if d > 0 else ((self.mm + 4) // 5 * 5 - 5) % 60
        self._show()

    def _show(self) -> None:
        self._hh_label.text = f"{self.hh:02d}"
        self._mm_label.text = f"{self.mm:02d}"


@dataclass
class Field:
    key: str
    label: str
    kind: str = "text"  # text | number | priority | time
    value: Any = ""
    suggest: bool = False  # text only: keyboard word completion + spellcheck


def form(title: str, fields: Sequence[Field], on_submit: Callable[[dict[str, Any]], None],
         submit_text: str = "Save") -> None:
    """Dialog with ``fields``. ``on_submit(values)`` may raise ValueError to show a message."""
    content = MDBoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None,
                          height=dp(64 * sum(1 for f in fields if f.kind != "priority")
                                    + 52 * sum(1 for f in fields if f.kind == "priority")))
    widgets: dict[str, Any] = {}
    for f in fields:
        if f.kind == "priority":
            w: Any = PriorityPicker(int(f.value or 1))
        elif f.kind == "time":
            w = TimeStepper(f.label, f.value or "09:00")
        else:
            extra = {"input_type": "text", "keyboard_suggestions": True} if f.suggest else {}
            w = MDTextField(hint_text=f.label, text="" if f.value is None else str(f.value),
                            input_filter="float" if f.kind == "number" else None,
                            mode="rectangle", write_tab=False, **extra)
            w.text_color_normal = w.text_color_focus = DARK_TEXT
            w.hint_text_color_normal = (0.25, 0.25, 0.25, 1)
            w.line_color_normal = (0.25, 0.25, 0.25, 1)
        widgets[f.key] = w
        content.add_widget(w)
    dialog: MDDialog

    def submit(*_a: Any) -> None:
        values = {k: (w.value if isinstance(w, (PriorityPicker, TimeStepper)) else w.text)
                  for k, w in widgets.items()}
        try:
            on_submit(values)
        except ValueError as exc:
            toast(str(exc))
            return
        dialog.dismiss()

    dialog = _dialog(title, content, [
        MDFlatButton(text="Cancel", on_release=lambda *_: dialog.dismiss()),
        MDRaisedButton(text=submit_text, on_release=submit)], pin_top=True)
    first = next((w for w in widgets.values() if isinstance(w, MDTextField)), None)
    if first is not None:
        Clock.schedule_once(lambda _dt: setattr(first, "focus", True), 0.3)
