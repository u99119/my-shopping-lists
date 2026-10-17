"""Home screen: all shopping lists."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFloatingActionButton, MDIconButton
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar
from kivy.utils import escape_markup

from ..core.currency import format_money
from ..core.models import ShoppingList
from ..core.viewmodel import list_summary
from .widgets import GREY, Field, Row, confirm, form, label, menu, toast


class HomeScreen(MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="home", **kwargs)
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(
            title="My Shopping Lists", elevation=2,
            right_action_items=[["shape-outline", lambda _w: self.app.open_screen("catalog")],
                                ["cog", lambda _w: self.app.open_screen("settings")]]))
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        scroll = ScrollView()
        scroll.add_widget(self.body)
        stack = MDFloatLayout()
        scroll.size_hint = (1, 1)
        stack.add_widget(scroll)
        stack.add_widget(MDFloatingActionButton(
            icon="plus", pos_hint={"right": 0.95, "y": 0.04},
            on_release=lambda *_: self.new_list()))
        root.add_widget(stack)
        self.add_widget(root)

    @property
    def app(self) -> Any:  # type: ignore[override]
        return MDApp.get_running_app()

    def on_pre_enter(self, *_args: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.body.clear_widgets()
        lists = self.app.repo.list_shopping_lists()
        if not lists:
            self.body.add_widget(Row(height=80, padding=(dp(16), 0, 0, 0)))
            self.body.children[0].add_widget(label(
                f"[color={GREY}]No lists yet. Tap + to create one.[/color]"))
        for sl in lists:
            self.body.add_widget(self._row(sl))

    def _row(self, sl: ShoppingList) -> Row:
        t = list_summary(self.app.repo, sl.id)
        sub = f"{t.bought}/{t.total} bought"
        if t.cost_total:
            sub += f" · {format_money(t.cost_total, sl.currency)}"
        row = Row(on_tap=lambda: self.app.open_list(sl.id), height=68)
        row.add_widget(label(f"[b]{escape_markup(sl.name)}[/b]\n"
                             f"[size=12sp][color={GREY}]{sub}[/color][/size]"))
        dots = MDIconButton(icon="dots-vertical", pos_hint={"center_y": 0.5})
        dots.bind(on_release=lambda w: self.row_menu(w, sl))
        row.add_widget(dots)
        return row

    def new_list(self) -> None:
        sl = self.app.repo.create_list()
        self.app.open_list(sl.id)

    def row_menu(self, caller: Any, sl: ShoppingList) -> None:
        menu(caller, [
            ("Open", lambda: self.app.open_list(sl.id)),
            ("Rename", lambda: self.rename(sl)),
            ("Duplicate (reset status)", lambda: self.duplicate(sl)),
            ("Share", lambda: self.app.share_list(sl.id, True)),
            ("Delete", lambda: confirm("Delete list", f"Delete '{sl.name}' and all its items?",
                                       lambda: self._then(self.app.repo.delete_list, sl.id))),
        ])

    def rename(self, sl: ShoppingList) -> None:
        form("Rename list", [Field("name", "List name", value=sl.name)],
             lambda v: self._then(self.app.repo.rename_list, sl.id, v["name"]))

    def duplicate(self, sl: ShoppingList) -> None:
        copy = self.app.repo.duplicate_list(sl.id)
        toast(f"Created '{copy.name}'")
        self.refresh()

    def _then(self, fn: Any, *args: Any) -> None:
        fn(*args)
        self.refresh()
