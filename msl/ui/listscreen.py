"""The screen showing one shopping list, in view mode or edit mode."""

from __future__ import annotations

from typing import Any, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.screen import MDScreen
from kivymd.uix.toolbar import MDTopAppBar

from ..core.viewmodel import CategoryView, ListView, build_list_view
from .listactions import ListActions
from .listrows import category_header, counts, item_row, note, subcategory_header
from .widgets import Field, form, label, menu


class ListScreen(ListActions, MDScreen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="list", **kwargs)
        self.list_id = ""
        self.edit_mode = False
        self.expanded: set[str] = set()
        self.view: Optional[ListView] = None

        root = MDBoxLayout(orientation="vertical")
        self.bar = MDTopAppBar(
            title="", elevation=2,
            left_action_items=[["arrow-left", lambda _w: self.app.go_home()]],
            right_action_items=[["pencil", lambda _w: self.toggle_mode()],
                                ["dots-vertical", lambda w: self.list_menu(w)]])
        self.body = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True)
        self.scroll = ScrollView()
        self.scroll.add_widget(self.body)
        self.footer = label("", size_hint_y=None, height=dp(40), padding=(dp(16), 0))
        self.add_btn = MDRaisedButton(text="Add category", pos_hint={"center_x": 0.5},
                                      on_release=lambda *_: self.add_category())
        self.bottom = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True,
                                  padding=(0, 0, 0, dp(8)), spacing=dp(4))
        for w in (self.footer, self.add_btn):
            self.bottom.add_widget(w)
        for w in (self.bar, self.scroll, self.bottom):
            root.add_widget(w)
        self.add_widget(root)

    @property
    def app(self) -> Any:  # type: ignore[override]
        return MDApp.get_running_app()

    @property
    def currency(self) -> str:
        return self.view.shopping_list.currency if self.view else "INR"

    # ------------------------------------------------------------ lifecycle
    def open_list(self, list_id: str) -> None:
        self.list_id, self.edit_mode = list_id, False
        self.expanded.clear()
        self.refresh()

    def toggle_mode(self) -> None:
        self.edit_mode = not self.edit_mode
        self.refresh()

    def toggle_expand(self, key: str) -> None:
        self.expanded.symmetric_difference_update({key})
        self.refresh()

    # --------------------------------------------------------------- render
    def refresh(self) -> None:
        view = build_list_view(self.app.repo, self.list_id)
        if view is None:
            self.app.go_home()
            return
        self.view = view
        y = self.scroll.scroll_y
        self.bar.title = view.shopping_list.name
        self.bar.right_action_items = [
            ["eye" if self.edit_mode else "pencil", lambda _w: self.toggle_mode()],
            ["dots-vertical", lambda w: self.list_menu(w)]]
        self.add_btn.opacity = 1 if self.edit_mode else 0
        self.add_btn.disabled = not self.edit_mode
        self.add_btn.height = dp(48) if self.edit_mode else 0
        self.body.clear_widgets()
        for cv in view.categories:
            self._render_category(cv)
        if not view.categories:
            self.body.add_widget(note("Nothing here yet. Tap the pencil, then 'Add category'."))
        self.footer.text = "  " + counts(view.totals, view.shopping_list.currency)
        Clock.schedule_once(lambda _dt: setattr(self.scroll, "scroll_y", y), 0)

    def _render_category(self, cv: CategoryView) -> None:
        lc = cv.category
        full = self.edit_mode or lc.id in self.expanded
        self.body.add_widget(category_header(self, cv, full))
        if cv.totals.total == 0:
            self.body.add_widget(note("No items yet"))
        elif not full:
            if not cv.collapsed_rows:
                self.body.add_widget(note("All done"))
            for sub_name, item in cv.collapsed_rows:
                self.body.add_widget(item_row(self, item, sub_name))
            return
        if not full:
            return
        for item in cv.direct_items:
            self.body.add_widget(item_row(self, item))
        for sv in cv.subcategories:
            self.body.add_widget(subcategory_header(self, sv))
            for item in sv.items:
                self.body.add_widget(item_row(self, item, indent=48))
            if not sv.items and self.edit_mode:
                self.body.add_widget(note("No items"))

    # ---------------------------------------------------------- list actions
    def list_menu(self, caller: Any) -> None:
        menu(caller, [
            ("Share full list", lambda: self.app.share_list(self.list_id, True)),
            ("Share remaining only", lambda: self.app.share_list(self.list_id, False)),
            ("Rename list", self.rename),
            ("Change currency", self.change_currency),
        ])

    def rename(self) -> None:
        sl = self.view.shopping_list  # type: ignore[union-attr]
        form("Rename list", [Field("name", "List name", value=sl.name)],
             lambda v: self._apply(lambda: self.app.repo.rename_list(sl.id, v["name"])))

    def change_currency(self) -> None:
        sl = self.view.shopping_list  # type: ignore[union-attr]
        form("Currency (3-letter code)", [Field("code", "e.g. INR, USD, JPY", value=sl.currency)],
             lambda v: self._apply(lambda: self.app.repo.set_list_currency(sl.id, v["code"])))
