"""Row builders for the list screen (category / sub-category headers and item rows)."""

from __future__ import annotations

from typing import Optional

from kivy.metrics import dp
from kivy.utils import escape_markup
from kivymd.uix.button import MDIconButton

from ..core.currency import format_money
from ..core.models import Item, Status
from ..core.viewmodel import CategoryView, SubcategoryView, Totals
from .widgets import GREY, Bullet, Row, dot, label

HEADER_BG = (0.88, 0.95, 0.95, 1)
SUB_BG = (0.95, 0.97, 0.97, 1)
TEAL = (0.0, 0.47, 0.42, 1)
RED = (0.90, 0.22, 0.21, 1)
GREEN = (0.26, 0.63, 0.28, 1)
ORANGE = (0.98, 0.55, 0.0, 1)


class _RoundButton(MDIconButton):
    """Compact circular icon button (KivyMD's default is 48 dp, too tall for tight rows)."""

    def set_size(self, interval) -> None:
        self.width = self.height = dp(34)


def _dots(callback) -> MDIconButton:
    btn = _RoundButton(icon="dots-vertical", icon_size="20sp", pos_hint={"center_y": 0.5})
    btn.bind(on_release=lambda w: callback(w))
    return btn


def _quick(icon: str, callback, color=None) -> MDIconButton:
    """Small icon button used for the quick actions next to the three-dot menu."""
    btn = _RoundButton(icon=icon, icon_size="20sp", pos_hint={"center_y": 0.5})
    if color:
        btn.theme_icon_color = "Custom"
        btn.icon_color = color
    btn.bind(on_release=lambda _w: callback())
    return btn


def counts(t: Totals, currency: str) -> str:
    text = f"{t.remaining} left of {t.total}"
    if t.cost_remaining:
        text += f" · {format_money(t.cost_remaining, currency)}"
    return text


def category_header(screen, cv: CategoryView, expanded: bool) -> Row:
    lc = cv.category
    row = Row(on_tap=lambda: screen.toggle_expand(lc.id), height=48, md_bg_color=HEADER_BG,
              padding=(dp(4), 0, 0, 0))
    icon = _RoundButton(icon="chevron-down" if expanded else "chevron-right",
                        icon_size="20sp", pos_hint={"center_y": 0.5}, disabled=True)
    row.add_widget(icon)
    row.add_widget(Bullet("category"))
    row.add_widget(label(
        f"{dot(lc.priority)} [b]{escape_markup(lc.name)}[/b]\n"
        f"[size=12sp][color={GREY}]{counts(cv.totals, screen.currency)}[/color][/size]"))
    if screen.edit_mode:
        # plus inside a circle = add item (items are circles); plus inside a square = add sub-category
        row.add_widget(_quick("plus-circle-outline", lambda: screen.add_item(lc.id), TEAL))
        row.add_widget(_quick("plus-box-outline", lambda: screen.add_subcategory(cv), TEAL))
        row.add_widget(_quick("minus-circle-outline", lambda: screen.remove_category(cv), RED))
        row.add_widget(_dots(lambda w: screen.category_menu(w, cv)))
    return row


def subcategory_header(screen, sv: SubcategoryView) -> Row:
    ls = sv.subcategory
    row = Row(height=38, md_bg_color=SUB_BG, padding=(dp(40), 0, 0, 0))
    row.add_widget(Bullet("subcategory"))
    row.add_widget(label(
        f"{dot(ls.priority)} [b]{escape_markup(ls.name)}[/b]  "
        f"[size=12sp][color={GREY}]{counts(sv.totals, screen.currency)}[/color][/size]"))
    if screen.edit_mode:
        row.add_widget(_quick("plus-circle-outline",
                              lambda: screen.add_item(ls.list_category_id, ls.id), TEAL))
        row.add_widget(_quick("minus-circle-outline", lambda: screen.remove_subcategory(sv), RED))
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
              height=46 if subtitle else 38, padding=(dp(indent), 0, 0, 0))
    row.add_widget(Bullet("item"))
    row.add_widget(label(item_text(item, subtitle)))
    if item.cost is not None:
        row.add_widget(label(format_money(item.cost, screen.currency), halign="right",
                             size_hint_x=None, width=dp(72)))
    bought = item.status is Status.BOUGHT
    unavailable = item.status is Status.NOT_AVAILABLE
    row.add_widget(_quick("check-circle" if bought else "check-circle-outline",
                          lambda: screen.toggle_bought(item), GREEN if bought else None))
    row.add_widget(_quick("close-circle" if unavailable else "close-circle-outline",
                          lambda: screen.toggle_not_available(item), ORANGE if unavailable else None))
    row.add_widget(_quick("minus-circle-outline", lambda: screen.delete_item(item), RED))
    row.add_widget(_dots(lambda w: screen.item_menu(w, item)))
    return row


def note(text: str) -> Row:
    row = Row(height=32, padding=(dp(56), 0, 0, 0))
    row.add_widget(label(f"[color={GREY}][i]{text}[/i][/color]"))
    return row
