"""Read-only, UI-friendly snapshots of a shopping list (sorting, collapsing, totals)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .models import Item, ListCategory, ListSubcategory, ShoppingList, Status
from .repository import Repository


def item_sort_key(item: Item) -> tuple:
    """Priority first, open items before closed ones, then insertion order."""
    return (int(item.priority), not item.status.is_open, item.created_at)


def top_priority_items(items: Iterable[Item]) -> list[Item]:
    """All *pending* items sharing the highest (numerically lowest) priority."""
    pending = [i for i in items if i.status.is_open]
    if not pending:
        return []
    best = min(int(i.priority) for i in pending)
    return sorted((i for i in pending if int(i.priority) == best), key=item_sort_key)


@dataclass
class Totals:
    total: int = 0
    remaining: int = 0
    bought: int = 0
    not_available: int = 0
    cost_total: float = 0.0
    cost_remaining: float = 0.0

    def add_item(self, item: Item) -> None:
        self.total += 1
        cost = item.cost or 0.0
        if item.status is Status.BOUGHT:
            self.bought += 1
        elif item.status is Status.NOT_AVAILABLE:
            self.not_available += 1
        if item.status is not Status.NOT_AVAILABLE:
            self.cost_total += cost
        if item.status.is_open:
            self.remaining += 1
            self.cost_remaining += cost

    def merge(self, other: "Totals") -> None:
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(self, name) + getattr(other, name))


@dataclass
class SubcategoryView:
    subcategory: ListSubcategory
    items: list[Item]
    totals: Totals

    @property
    def collapsed_items(self) -> list[Item]:
        return top_priority_items(self.items)


@dataclass
class CategoryView:
    category: ListCategory
    subcategories: list[SubcategoryView]
    direct_items: list[Item]
    totals: Totals

    @property
    def collapsed_rows(self) -> list[tuple[Optional[str], Item]]:
        """Collapsed view: top pending item(s) of each sub-category + top pending direct items.

        Returns ``(subcategory_name_or_None, item)`` pairs sorted by priority.
        """
        rows: list[tuple[Optional[str], Item]] = []
        for sv in self.subcategories:
            rows.extend((sv.subcategory.name, i) for i in sv.collapsed_items)
        rows.extend((None, i) for i in top_priority_items(self.direct_items))
        return sorted(rows, key=lambda r: item_sort_key(r[1]))


@dataclass
class ListView:
    shopping_list: ShoppingList
    categories: list[CategoryView] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)


def build_category_view(repo: Repository, lc: ListCategory) -> CategoryView:
    items = repo.items_for_list_category(lc.id)
    by_sub: dict[Optional[str], list[Item]] = {}
    for item in items:
        by_sub.setdefault(item.list_subcategory_id, []).append(item)

    sub_views: list[SubcategoryView] = []
    for ls in repo.list_subcategories(lc.id):
        sub_items = sorted(by_sub.get(ls.id, []), key=item_sort_key)
        totals = Totals()
        for i in sub_items:
            totals.add_item(i)
        sub_views.append(SubcategoryView(ls, sub_items, totals))

    direct = sorted(by_sub.get(None, []), key=item_sort_key)
    cat_totals = Totals()
    for i in direct:
        cat_totals.add_item(i)
    for sv in sub_views:
        cat_totals.merge(sv.totals)
    return CategoryView(lc, sub_views, direct, cat_totals)


def build_list_view(repo: Repository, list_id: str) -> Optional[ListView]:
    sl = repo.get_list(list_id)
    if sl is None:
        return None
    view = ListView(sl)
    for lc in repo.list_categories(list_id):
        cv = build_category_view(repo, lc)
        view.categories.append(cv)
        view.totals.merge(cv.totals)
    return view


def list_summary(repo: Repository, list_id: str) -> Totals:
    totals = Totals()
    for item in repo.items_for_list(list_id):
        totals.add_item(item)
    return totals
