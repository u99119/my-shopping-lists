"""Human-readable plain-text rendering of a list (for WhatsApp / e-mail sharing)."""

from __future__ import annotations

from .currency import format_money
from .models import Item, Status
from .viewmodel import ListView

_MARK = {Status.PENDING: "☐", Status.BOUGHT: "☑", Status.NOT_AVAILABLE: "✗"}
_PRIORITY_TAG = {1: "", 2: " (good to have)", 3: " (can avoid)"}


def _item_line(item: Item, currency: str, indent: str) -> str:
    cost = f" — {format_money(item.cost, currency)}" if item.cost is not None else ""
    suffix = " [not available]" if item.status is Status.NOT_AVAILABLE else ""
    tag = _PRIORITY_TAG[int(item.priority)]
    return f"{indent}{_MARK[item.status]} {item.name}{tag}{cost}{suffix}"


def format_list_text(view: ListView, include_closed: bool = True) -> str:
    """Render a :class:`ListView` as plain text.

    ``include_closed=False`` omits bought / not-available items (a "still to buy" list).
    """
    cur = view.shopping_list.currency
    lines = [f"🛒 {view.shopping_list.name}", ""]

    def keep(item: Item) -> bool:
        return include_closed or item.status.is_open

    for cv in view.categories:
        cat_lines: list[str] = []
        for item in cv.direct_items:
            if keep(item):
                cat_lines.append(_item_line(item, cur, "  "))
        for sv in cv.subcategories:
            sub_items = [i for i in sv.items if keep(i)]
            if not sub_items:
                continue
            cat_lines.append(f"  ▸ {sv.subcategory.name}")
            cat_lines.extend(_item_line(i, cur, "    ") for i in sub_items)
        if not cat_lines:
            continue
        lines.append(f"*{cv.category.name}*{_PRIORITY_TAG[int(cv.category.priority)]}")
        lines.extend(cat_lines)
        lines.append("")

    t = view.totals
    lines.append(f"Items: {t.total} · bought {t.bought} · remaining {t.remaining}")
    if t.cost_total:
        lines.append(
            f"Approx. total {format_money(t.cost_total, cur)}"
            f" · remaining {format_money(t.cost_remaining, cur)}"
        )
    return "\n".join(lines).rstrip() + "\n"
