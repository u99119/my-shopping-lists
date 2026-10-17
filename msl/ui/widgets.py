"""Small reusable UI pieces: rows, menus, dialogs and forms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineAvatarListItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.textfield import MDTextField

from ..core.models import Priority

PRIORITY_COLOR = {1: "e53935", 2: "fb8c00", 3: "43a047"}  # red, orange, green
GREY = "9e9e9e"


def dot(priority: int) -> str:
    return f"[color={PRIORITY_COLOR[int(priority)]}]●[/color]"


class Row(ButtonBehavior, MDBoxLayout):
    """A fixed-height horizontal row that can be tapped."""

    def __init__(self, on_tap: Optional[Callable[[], None]] = None, height: float = 56,
                 **kwargs: Any) -> None:
        kwargs.setdefault("padding", (dp(12), 0, 0, 0))
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(height),
                         spacing=dp(4), **kwargs)
        if on_tap:
            self.bind(on_release=lambda *_: on_tap())


def label(text: str, **kwargs: Any) -> MDLabel:
    return MDLabel(text=text, markup=True, valign="center", **kwargs)


class TextButton(ButtonBehavior, MDLabel):
    """A compact tappable text such as ``+I`` (fixed width, so rows stay narrow)."""

    def __init__(self, text: str, on_tap: Callable[[], None], width: float = 34,
                 color: str = "00796b", **kwargs: Any) -> None:
        super().__init__(text=f"[b][color={color}]{text}[/color][/b]", markup=True,
                         halign="center", valign="center", size_hint=(None, 1),
                         width=dp(width), **kwargs)
        self.bind(on_release=lambda *_: on_tap())


def toast(message: str) -> None:
    MDSnackbar(MDLabel(text=message, theme_text_color="Custom",
                       text_color=(1, 1, 1, 1))).open()


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


def _dialog(title: str, content=None, buttons=(), **kwargs: Any) -> MDDialog:
    dialog = MDDialog(title=title, buttons=list(buttons), **(
        {"type": "custom", "content_cls": content} if content is not None else {}), **kwargs)
    dialog.open()
    return dialog


def confirm(title: str, text: str, on_yes: Callable[[], None], yes_text: str = "Delete") -> None:
    dialog: MDDialog

    def yes(*_a: Any) -> None:
        dialog.dismiss()
        on_yes()

    dialog = MDDialog(
        title=title, text=text,
        buttons=[MDFlatButton(text="Cancel", on_release=lambda *_: dialog.dismiss()),
                 MDRaisedButton(text=yes_text, on_release=yes)],
    )
    dialog.open()


def choose(title: str, options: Sequence[tuple[str, Any]], on_pick: Callable[[Any], None]) -> None:
    """Dialog listing ``(label, value)`` options; calls ``on_pick(value)``."""
    dialog: MDDialog

    def pick(value: Any) -> None:
        dialog.dismiss()
        Clock.schedule_once(lambda _dt: on_pick(value), 0.05)

    dialog = MDDialog(
        title=title, type="simple",
        # MDDialog "simple" needs items that own a ``_left_container`` (avatar list items).
        items=[OneLineAvatarListItem(text=text, on_release=(lambda _w, v=value: pick(v)))
               for text, value in options],
    )
    dialog.open()


class PriorityPicker(MDBoxLayout):
    """Three buttons: 1 Must have, 2 Good to have, 3 Can avoid."""

    def __init__(self, value: int = 1, **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(48),
                         spacing=dp(6), **kwargs)
        self.value = int(value)
        self._buttons: dict[int, MDRaisedButton] = {}
        for p in Priority:
            btn = MDRaisedButton(text=f"{int(p)} {p.label}", font_size="12sp",
                                 on_release=lambda _b, p=int(p): self.select(p))
            self._buttons[int(p)] = btn
            self.add_widget(btn)
        self.select(self.value)

    def select(self, value: int) -> None:
        self.value = value
        for p, btn in self._buttons.items():
            btn.md_bg_color = (0.0, 0.5, 0.5, 1) if p == value else (0.6, 0.6, 0.6, 1)


@dataclass
class Field:
    key: str
    label: str
    kind: str = "text"  # text | number | priority
    value: Any = ""


def form(title: str, fields: Sequence[Field], on_submit: Callable[[dict[str, Any]], None],
         submit_text: str = "Save") -> None:
    """Dialog with ``fields``. ``on_submit(values)`` may raise ValueError to show a message."""
    content = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None,
                          height=dp(72 * sum(1 for f in fields if f.kind != "priority")
                                    + 60 * sum(1 for f in fields if f.kind == "priority")))
    widgets: dict[str, Any] = {}
    for f in fields:
        if f.kind == "priority":
            w: Any = PriorityPicker(int(f.value or 1))
        else:
            w = MDTextField(hint_text=f.label, text="" if f.value is None else str(f.value),
                            input_filter="float" if f.kind == "number" else None,
                            mode="rectangle", write_tab=False)
        widgets[f.key] = w
        content.add_widget(w)
    dialog: MDDialog

    def submit(*_a: Any) -> None:
        values = {k: (w.value if isinstance(w, PriorityPicker) else w.text)
                  for k, w in widgets.items()}
        try:
            on_submit(values)
        except ValueError as exc:
            toast(str(exc))
            return
        dialog.dismiss()

    dialog = _dialog(title, content, [
        MDFlatButton(text="Cancel", on_release=lambda *_: dialog.dismiss()),
        MDRaisedButton(text=submit_text, on_release=submit)])
    first = next((w for w in widgets.values() if isinstance(w, MDTextField)), None)
    if first is not None:
        Clock.schedule_once(lambda _dt: setattr(first, "focus", True), 0.3)
