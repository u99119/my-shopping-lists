"""User actions on a shopping list: add / edit / remove categories, sub-categories, items."""

from __future__ import annotations

from typing import Any, Callable

from ..core.models import Item, Priority, Status
from ..core.viewmodel import CategoryView, SubcategoryView
from .widgets import Field, choose, confirm, form, menu

PRIORITY_OPTIONS = [(f"{int(p)} – {p.label}", int(p)) for p in Priority]


class ListActions:
    """Mixin for ``ListScreen``; expects ``app``, ``list_id`` and ``refresh()``."""

    app: Any
    list_id: str

    def refresh(self) -> None:  # provided by ListScreen
        raise NotImplementedError

    def _apply(self, change: Callable[[], object]) -> None:
        """Run a repository change (ValueError is shown by ``form``/caller), then redraw."""
        change()
        self.refresh()

    # ---------------------------------------------------------------- add
    def add_category(self) -> None:
        repo = self.app.repo
        used = {lc.category_id for lc in repo.list_categories(self.list_id)}
        options: list[tuple[str, Any]] = [
            (c.name, c.id) for c in repo.list_catalog_categories() if c.id not in used]
        options.append(("➕ New category…", None))

        def picked(category_id: Any) -> None:
            fields = [Field("priority", "Priority", "priority", 1)]
            if category_id is None:
                fields.insert(0, Field("name", "Category name"))

            def save(v: dict) -> None:
                cid = category_id or repo.get_or_create_catalog_category(v["name"]).id
                self._apply(lambda: repo.add_list_category(self.list_id, cid, v["priority"]))

            form("Add category" if category_id is None else "Category priority", fields, save, "Add")

        choose("Add category", options, picked)

    def add_subcategory(self, cv: CategoryView) -> None:
        repo, lc = self.app.repo, cv.category
        used = {s.subcategory.subcategory_id for s in cv.subcategories}
        options: list[tuple[str, Any]] = [
            (s.name, s.id) for s in repo.list_catalog_subcategories(lc.category_id)
            if s.id not in used]
        options.append(("➕ New sub-category…", None))

        def picked(sub_id: Any) -> None:
            fields = [Field("priority", "Priority", "priority", 1)]
            if sub_id is None:
                fields.insert(0, Field("name", "Sub-category name"))

            def save(v: dict) -> None:
                sid = sub_id or repo.get_or_create_catalog_subcategory(
                    lc.category_id, v["name"]).id
                self._apply(lambda: repo.add_list_subcategory(lc.id, sid, v["priority"]))

            form("Add sub-category" if sub_id is None else "Sub-category priority",
                 fields, save, "Add")

        choose("Add sub-category", options, picked)

    def add_item(self, list_category_id: str, list_subcategory_id: str | None = None) -> None:
        def save(v: dict) -> None:
            self._apply(lambda: self.app.repo.add_item(
                list_category_id, v["name"], v["priority"], v["cost"], list_subcategory_id))

        form("Add item", [Field("name", "Item name"), Field("cost", "Approx. cost (optional)",
                                                             "number"),
                          Field("priority", "Priority", "priority", 1)], save, "Add")

    def edit_item(self, item: Item) -> None:
        def save(v: dict) -> None:
            self._apply(lambda: self.app.repo.update_item(
                item.id, v["name"], v["priority"], v["cost"]))

        form("Edit item", [Field("name", "Item name", value=item.name),
                           Field("cost", "Approx. cost (optional)", "number",
                                 "" if item.cost is None else item.cost),
                           Field("priority", "Priority", "priority", int(item.priority))], save)

    # ------------------------------------------------------------ status
    def set_status(self, item: Item, status: Status) -> None:
        self.app.repo.set_item_status(item.id, status)
        self.refresh()

    # ------------------------------------------------------------- menus
    def item_menu(self, caller: Any, item: Item) -> None:
        entries = [
            ("Mark pending" if item.status is Status.BOUGHT else "Mark bought",
             lambda: self.set_status(
                 item, Status.PENDING if item.status is Status.BOUGHT else Status.BOUGHT)),
            ("Mark available" if item.status is Status.NOT_AVAILABLE else "Not available",
             lambda: self.set_status(
                 item, Status.PENDING if item.status is Status.NOT_AVAILABLE
                 else Status.NOT_AVAILABLE)),
            ("Edit", lambda: self.edit_item(item)),
            ("Delete", lambda: confirm("Delete item", f"Delete '{item.name}'?",
                                       lambda: self._apply(
                                           lambda: self.app.repo.delete_item(item.id)))),
        ]
        menu(caller, entries)

    def category_menu(self, caller: Any, cv: CategoryView) -> None:
        lc, repo = cv.category, self.app.repo
        menu(caller, [
            ("Add item", lambda: self.add_item(lc.id)),
            ("Add sub-category", lambda: self.add_subcategory(cv)),
            ("Set priority", lambda: choose("Priority", PRIORITY_OPTIONS, lambda p: self._apply(
                lambda: repo.set_list_category_priority(lc.id, p)))),
            ("Remove from list", lambda: confirm(
                "Remove category", f"Remove '{lc.name}' and its items from this list?",
                lambda: self._apply(lambda: repo.remove_list_category(lc.id)), "Remove")),
        ])

    def sub_menu(self, caller: Any, sv: SubcategoryView) -> None:
        ls, repo = sv.subcategory, self.app.repo
        menu(caller, [
            ("Add item", lambda: self.add_item(ls.list_category_id, ls.id)),
            ("Set priority", lambda: choose("Priority", PRIORITY_OPTIONS, lambda p: self._apply(
                lambda: repo.set_list_subcategory_priority(ls.id, p)))),
            ("Remove from category", lambda: confirm(
                "Remove sub-category", f"Remove '{ls.name}' and its items?",
                lambda: self._apply(lambda: repo.remove_list_subcategory(ls.id)), "Remove")),
        ])
