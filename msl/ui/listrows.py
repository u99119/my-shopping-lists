"""Row builders for the list screen (category / sub-category headers and item rows)."""

from __future__ import annotations

from typing import Optional

from kivy.metrics import dp
from kivy.utils import escape_markup
from kivymd.uix.button import MDIconButton
from kivymd.uix.selectioncontrol import MDCheckbox

from ..core.currency import format_money
from ..core.models import Item, Status
from ..core.viewmodel import CategoryView, SubcategoryView, Totals
from .widgets import GREY, Row, dot, label

HEADER_BG = (0.88, 0.95, 0.95, 1)
SUB_BG = (0.95, 0.97, 0.97, 1)


def _dots(callback) -> MDIconButton:
    btn = MDIconButton(icon="dots-vertical", pos_hint={"center_y": 0.5})
    btn.bind(on_release=lambda w: callback(w))
    return btn


def counts(t: Totals, currency: str) -> str:
    text = f"{t.remaining} left of {t.total}"
    if t.cost_remaining:
        text += f" · {format_money(t.cost_remaining, currency)}"
    return text


def category_header(screen, cv: CategoryView, expanded: bool) -> Row:
    lc = cv.category
    row = Row(on_tap=lambda: screen.toggle_expand(lc.id), height=60, md_bg_color=HEADER_BG)
    icon = MDIconButton(icon="chevron-down" if expanded else "chevron-right",
                        pos_hint={"center_y": 0.5}, disabled=True)
    row.add_widget(icon)
    row.add_widget(label(
        f"{dot(lc.priority)} [b]{escape_markup(lc.name)}[/b]\n"
        f"[size=12sp][color={GREY}]{counts(cv.totals, screen.currency)}[/color][/size]"))
    if screen.edit_mode:
        row.add_widget(_dots(lambda w: screen.category_menu(w, cv)))
    return row


def subcategory_header(screen, sv: SubcategoryView) -> Row:
    ls = sv.subcategory
    row = Row(height=44, md_bg_color=SUB_BG, padding=(dp(44), 0, 0, 0))
    row.add_widget(label(
        f"{dot(ls.priority)} [b]{escape_markup(ls.name)}[/b]  "
        f"[size=12sp][color={GREY}]{counts(sv.totals, screen.currency)}[/color][/size]"))
    if screen.edit_mode:
        row.add_widget(_dots(lambda w: screen.sub_menu(w, sv)))
    return row


def item_text(item: Item, subtitle: Optional[str] = None) -> str:
    name = escape_markup(item.name)
    if item.status is Status.BOUGHT:
        text = f"[color={GREY}][s]{name}[/s][/color]"
    elif item.status is Status.NOT_AVAILABLE:
        text = f"[color={GREY}]{name}  (not available)[/color]"
    else:
        text = f"{dot(item.priority)} {name}"
    if subtitle:
        text += f"\n[size=12sp][color={GREY}]{escape_markup(subtitle)}[/color][/size]"
    return text


def item_row(screen, item: Item, subtitle: Optional[str] = None, indent: int = 24) -> Row:
    row = Row(on_tap=lambda: screen.edit_item(item) if screen.edit_mode else None,
              height=60 if subtitle else 52, padding=(dp(indent), 0, 0, 0))
    if not screen.edit_mode:
        box = MDCheckbox(active=item.status is Status.BOUGHT, size_hint=(None, None),
                         size=(dp(40), dp(40)), pos_hint={"center_y": 0.5})
        box.bind(active=lambda _w, on: screen.set_status(
            item, Status.BOUGHT if on else Status.PENDING))
        row.add_widget(box)
    row.add_widget(label(item_text(item, subtitle)))
    if item.cost is not None:
        row.add_widget(label(format_money(item.cost, screen.currency), halign="right",
                             size_hint_x=None, width=dp(88)))
    row.add_widget(_dots(lambda w: screen.item_menu(w, item)))
    return row


def note(text: str) -> Row:
    row = Row(height=40, padding=(dp(56), 0, 0, 0))
    row.add_widget(label(f"[color={GREY}][i]{text}[/i][/color]"))
    return row
