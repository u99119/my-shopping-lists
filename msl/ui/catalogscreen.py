"""Catalog screen: manage the reusable categories and their sub-categories."""

from __future__ import annotations

from typing import Any, Callable, Optional

from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFloatingActionButton, MDIconButton
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar

from .widgets import Field, Row, confirm, form, label, menu, toast


class CatalogScreen(MDScreen):
    """Two levels: categories, then the sub-categories of one category."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="catalog", **kwargs)
        self.category_id: Optional[str] = None
        root = MDBoxLayout(orientation="vertical")
        self.bar = MDTopAppBar(title="Categories", elevation=2,
                               left_action_items=[["arrow-left", lambda _w: self.on_back()]])
        root.add_widget(self.bar)
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        scroll = ScrollView()
        scroll.add_widget(self.body)
        stack = MDFloatLayout()
        stack.add_widget(scroll)
        stack.add_widget(MDFloatingActionButton(
            icon="plus", pos_hint={"right": 0.95, "y": 0.04},
            on_release=lambda *_: self.add()))
        root.add_widget(stack)
        self.add_widget(root)

    @property
    def app(self) -> Any:  # type: ignore[override]
        return MDApp.get_running_app()

    def on_pre_enter(self, *_args: Any) -> None:
        self.category_id = None
        self.refresh()

    def on_back(self) -> None:
        if self.category_id is None:
            self.app.go_home()
        else:
            self.category_id = None
            self.refresh()

    # --------------------------------------------------------------- render
    def refresh(self) -> None:
        repo = self.app.repo
        self.body.clear_widgets()
        if self.category_id is None:
            self.bar.title = "Categories"
            for c in repo.list_catalog_categories():
                self._row(c.name, lambda c=c: self.open_category(c.id), [
                    ("Sub-categories", lambda c=c: self.open_category(c.id)),
                    ("Rename", lambda c=c: self.rename(c.id, c.name, repo.rename_catalog_category)),
                    ("Delete", lambda c=c: self.delete(c.name, repo.delete_catalog_category, c.id)),
                ])
            return
        cat = repo.get_catalog_category(self.category_id)
        self.bar.title = f"{cat.name}: sub-categories" if cat else "Sub-categories"
        for s in repo.list_catalog_subcategories(self.category_id):
            self._row(s.name, None, [
                ("Rename", lambda s=s: self.rename(s.id, s.name, repo.rename_catalog_subcategory)),
                ("Delete", lambda s=s: self.delete(s.name, repo.delete_catalog_subcategory, s.id)),
            ])

    def _row(self, text: str, on_tap: Optional[Callable[[], None]], entries: list) -> None:
        row = Row(on_tap=on_tap, height=52)
        row.add_widget(label(escape_markup(text)))
        dots = MDIconButton(icon="dots-vertical", pos_hint={"center_y": 0.5})
        dots.bind(on_release=lambda w: menu(w, entries))
        row.add_widget(dots)
        self.body.add_widget(row)

    def open_category(self, category_id: str) -> None:
        self.category_id = category_id
        self.refresh()

    # -------------------------------------------------------------- actions
    def add(self) -> None:
        repo, parent = self.app.repo, self.category_id
        what = "category" if parent is None else "sub-category"

        def save(v: dict) -> None:
            if parent is None:
                repo.add_catalog_category(v["name"])
            else:
                repo.add_catalog_subcategory(parent, v["name"])
            self.refresh()

        form(f"New {what}", [Field("name", f"{what.capitalize()} name")], save, "Add")

    def rename(self, entity_id: str, current: str, action: Callable[[str, str], None]) -> None:
        def save(v: dict) -> None:
            action(entity_id, v["name"])
            self.refresh()

        form("Rename", [Field("name", "Name", value=current)], save)

    def delete(self, name: str, action: Callable[[str], None], entity_id: str) -> None:
        def run() -> None:
            try:
                action(entity_id)
            except ValueError as exc:  # InUseError etc.
                toast(str(exc))
            self.refresh()

        confirm("Delete", f"Delete '{name}'?", run)
