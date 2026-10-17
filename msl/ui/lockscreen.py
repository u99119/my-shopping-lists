"""Lock screen shown on start-up when "Require device lock" is on."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.screen import MDScreen

from .. import APP_NAME
from .widgets import label


class LockScreen(MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="lock", **kwargs)
        box = MDBoxLayout(orientation="vertical", spacing=dp(16), padding=dp(32),
                          adaptive_height=True, pos_hint={"center_x": 0.5, "center_y": 0.5})
        box.add_widget(label(f"[b]{APP_NAME}[/b]\nLocked", halign="center", adaptive_height=True))
        box.add_widget(MDRaisedButton(text="Unlock", pos_hint={"center_x": 0.5},
                                      on_release=lambda *_: self.unlock()))
        self.add_widget(box)

    def unlock(self) -> None:
        MDApp.get_running_app().ask_unlock()
