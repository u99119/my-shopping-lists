"""Data-access layer: all reads/writes go through :class:`Repository`."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Iterable, Optional

from .models import (
    CatalogCategory,
    CatalogSubcategory,
    Item,
    ListCategory,
    ListSubcategory,
    Priority,
    ShoppingList,
    Status,
    new_id,
    utc_now,
)

MAX_NAME_LEN = 100


class ValidationError(ValueError):
    """User-facing validation problem."""


class InUseError(ValidationError):
    """Entity cannot be deleted because other records reference it."""


def clean_name(name: object, what: str = "Name") -> str:
    text = " ".join(str(name or "").split())
    if not text:
        raise ValidationError(f"{what} cannot be empty.")
    if len(text) > MAX_NAME_LEN:
        raise ValidationError(f"{what} must be at most {MAX_NAME_LEN} characters.")
    return text


def clean_cost(cost: object) -> Optional[float]:
    if cost is None or (isinstance(cost, str) and not cost.strip()):
        return None
    try:
        value = float(str(cost).replace(",", "").strip())
    except ValueError as exc:
        raise ValidationError("Cost must be a number.") from exc
    if value < 0 or value != value or value in (float("inf"),):
        raise ValidationError("Cost must be zero or more.")
    return round(value, 2)


def clean_currency(code: object) -> str:
    text = str(code or "").strip().upper()
    if len(text) != 3 or not text.isalpha():
        raise ValidationError("Currency must be a 3-letter code, e.g. INR.")
    return text


def _priority(value: object) -> Priority:
    try:
        return Priority.coerce(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ meta
    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # --------------------------------------------------------------- catalog
    @staticmethod
    def _cat(row: sqlite3.Row) -> CatalogCategory:
        return CatalogCategory(name=row["name"], id=row["id"], updated_at=row["updated_at"])

    @staticmethod
    def _sub(row: sqlite3.Row) -> CatalogSubcategory:
        return CatalogSubcategory(
            category_id=row["category_id"], name=row["name"], id=row["id"],
            updated_at=row["updated_at"],
        )

    def list_catalog_categories(self) -> list[CatalogCategory]:
        rows = self.conn.execute("SELECT * FROM catalog_category ORDER BY name")
        return [self._cat(r) for r in rows]

    def get_catalog_category(self, category_id: str) -> Optional[CatalogCategory]:
        row = self.conn.execute(
            "SELECT * FROM catalog_category WHERE id = ?", (category_id,)
        ).fetchone()
        return self._cat(row) if row else None

    def find_catalog_category(self, name: str) -> Optional[CatalogCategory]:
        row = self.conn.execute(
            "SELECT * FROM catalog_category WHERE name = ?", (clean_name(name),)
        ).fetchone()
        return self._cat(row) if row else None

    def add_catalog_category(self, name: str) -> CatalogCategory:
        name = clean_name(name, "Category name")
        if self.find_catalog_category(name):
            raise ValidationError(f"Category '{name}' already exists.")
        cat = CatalogCategory(name=name)
        with self.conn:
            self.conn.execute(
                "INSERT INTO catalog_category(id, name, updated_at) VALUES (?, ?, ?)",
                (cat.id, cat.name, cat.updated_at),
            )
        return cat

    def get_or_create_catalog_category(self, name: str) -> CatalogCategory:
        return self.find_catalog_category(name) or self.add_catalog_category(name)

    def rename_catalog_category(self, category_id: str, name: str) -> None:
        name = clean_name(name, "Category name")
        existing = self.find_catalog_category(name)
        if existing and existing.id != category_id:
            raise ValidationError(f"Category '{name}' already exists.")
        with self.conn:
            self.conn.execute(
                "UPDATE catalog_category SET name = ?, updated_at = ? WHERE id = ?",
                (name, utc_now(), category_id),
            )

    def delete_catalog_category(self, category_id: str) -> None:
        used = self.conn.execute(
            "SELECT COUNT(DISTINCT list_id) FROM list_category WHERE category_id = ?",
            (category_id,),
        ).fetchone()[0]
        if used:
            raise InUseError(f"Category is used in {used} shopping list(s); remove it there first.")
        with self.conn:
            self.conn.execute("DELETE FROM catalog_category WHERE id = ?", (category_id,))

    def list_catalog_subcategories(self, category_id: str) -> list[CatalogSubcategory]:
        rows = self.conn.execute(
            "SELECT * FROM catalog_subcategory WHERE category_id = ? ORDER BY name",
            (category_id,),
        )
        return [self._sub(r) for r in rows]

    def get_catalog_subcategory(self, subcategory_id: str) -> Optional[CatalogSubcategory]:
        row = self.conn.execute(
            "SELECT * FROM catalog_subcategory WHERE id = ?", (subcategory_id,)
        ).fetchone()
        return self._sub(row) if row else None

    def find_catalog_subcategory(self, category_id: str, name: str) -> Optional[CatalogSubcategory]:
        row = self.conn.execute(
            "SELECT * FROM catalog_subcategory WHERE category_id = ? AND name = ?",
            (category_id, clean_name(name)),
        ).fetchone()
        return self._sub(row) if row else None

    def add_catalog_subcategory(self, category_id: str, name: str) -> CatalogSubcategory:
        name = clean_name(name, "Sub-category name")
        if not self.get_catalog_category(category_id):
            raise ValidationError("Category not found.")
        if self.find_catalog_subcategory(category_id, name):
            raise ValidationError(f"Sub-category '{name}' already exists.")
        sub = CatalogSubcategory(category_id=category_id, name=name)
        with self.conn:
            self.conn.execute(
                "INSERT INTO catalog_subcategory(id, category_id, name, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (sub.id, sub.category_id, sub.name, sub.updated_at),
            )
        return sub

    def get_or_create_catalog_subcategory(self, category_id: str, name: str) -> CatalogSubcategory:
        return self.find_catalog_subcategory(category_id, name) or self.add_catalog_subcategory(
            category_id, name
        )

    def rename_catalog_subcategory(self, subcategory_id: str, name: str) -> None:
        name = clean_name(name, "Sub-category name")
        sub = self.get_catalog_subcategory(subcategory_id)
        if not sub:
            raise ValidationError("Sub-category not found.")
        existing = self.find_catalog_subcategory(sub.category_id, name)
        if existing and existing.id != subcategory_id:
            raise ValidationError(f"Sub-category '{name}' already exists.")
        with self.conn:
            self.conn.execute(
                "UPDATE catalog_subcategory SET name = ?, updated_at = ? WHERE id = ?",
                (name, utc_now(), subcategory_id),
            )

    def delete_catalog_subcategory(self, subcategory_id: str) -> None:
        used = self.conn.execute(
            "SELECT COUNT(*) FROM list_subcategory WHERE subcategory_id = ?", (subcategory_id,)
        ).fetchone()[0]
        if used:
            raise InUseError(
                f"Sub-category is used in {used} shopping list(s); remove it there first."
            )
        with self.conn:
            self.conn.execute("DELETE FROM catalog_subcategory WHERE id = ?", (subcategory_id,))

    # -------------------------------------------------------- shopping lists
    @staticmethod
    def _list(row: sqlite3.Row) -> ShoppingList:
        return ShoppingList(
            name=row["name"], currency=row["currency"], id=row["id"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def list_shopping_lists(self) -> list[ShoppingList]:
        rows = self.conn.execute("SELECT * FROM shopping_list ORDER BY created_at DESC")
        return [self._list(r) for r in rows]

    def get_list(self, list_id: str) -> Optional[ShoppingList]:
        row = self.conn.execute("SELECT * FROM shopping_list WHERE id = ?", (list_id,)).fetchone()
        return self._list(row) if row else None

    def unique_list_name(self, base: str) -> str:
        names = {
            r["name"].lower() for r in self.conn.execute("SELECT name FROM shopping_list")
        }
        if base.lower() not in names:
            return base
        n = 2
        while f"{base} ({n})".lower() in names:
            n += 1
        return f"{base} ({n})"

    def default_list_name(self, today: Optional[date] = None) -> str:
        return self.unique_list_name(f"SL_{(today or date.today()).isoformat()}")

    def create_list(self, name: Optional[str] = None, currency: str = "INR") -> ShoppingList:
        name = clean_name(name, "List name") if name else self.default_list_name()
        sl = ShoppingList(name=name, currency=clean_currency(currency))
        with self.conn:
            self.conn.execute(
                "INSERT INTO shopping_list(id, name, currency, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sl.id, sl.name, sl.currency, sl.created_at, sl.updated_at),
            )
        return sl

    def rename_list(self, list_id: str, name: str) -> None:
        self._update_list(list_id, name=clean_name(name, "List name"))

    def set_list_currency(self, list_id: str, currency: str) -> None:
        self._update_list(list_id, currency=clean_currency(currency))

    def _update_list(self, list_id: str, **values: str) -> None:
        cols = ", ".join(f"{k} = ?" for k in values)
        with self.conn:
            self.conn.execute(
                f"UPDATE shopping_list SET {cols}, updated_at = ? WHERE id = ?",
                (*values.values(), utc_now(), list_id),
            )

    def delete_list(self, list_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM shopping_list WHERE id = ?", (list_id,))

    def duplicate_list(self, list_id: str, name: Optional[str] = None) -> ShoppingList:
        """Copy a list with all categories/items; item statuses reset to pending."""
        src = self.get_list(list_id)
        if not src:
            raise ValidationError("List not found.")
        new_name = clean_name(name, "List name") if name else self.unique_list_name(
            f"{src.name} copy"
        )
        dst = ShoppingList(name=new_name, currency=src.currency)
        now = utc_now()
        with self.conn:
            self.conn.execute(
                "INSERT INTO shopping_list(id, name, currency, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (dst.id, dst.name, dst.currency, dst.created_at, dst.updated_at),
            )
            lc_map: dict[str, str] = {}
            for lc in self.conn.execute(
                "SELECT * FROM list_category WHERE list_id = ?", (list_id,)
            ).fetchall():
                lc_map[lc["id"]] = new_id()
                self.conn.execute(
                    "INSERT INTO list_category(id, list_id, category_id, priority, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (lc_map[lc["id"]], dst.id, lc["category_id"], lc["priority"], now),
                )
            ls_map: dict[str, str] = {}
            for old_lc, new_lc in lc_map.items():
                for ls in self.conn.execute(
                    "SELECT * FROM list_subcategory WHERE list_category_id = ?", (old_lc,)
                ).fetchall():
                    ls_map[ls["id"]] = new_id()
                    self.conn.execute(
                        "INSERT INTO list_subcategory(id, list_category_id, subcategory_id, "
                        "priority, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (ls_map[ls["id"]], new_lc, ls["subcategory_id"], ls["priority"], now),
                    )
                for it in self.conn.execute(
                    "SELECT * FROM item WHERE list_category_id = ?", (old_lc,)
                ).fetchall():
                    self.conn.execute(
                        "INSERT INTO item(id, list_category_id, list_subcategory_id, name, "
                        "priority, cost, status, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            new_id(), new_lc, ls_map.get(it["list_subcategory_id"]),
                            it["name"], it["priority"], it["cost"], Status.PENDING.value,
                            now, now,
                        ),
                    )
        return dst

    # ------------------------------------------------------- list categories
    @staticmethod
    def _lc(row: sqlite3.Row) -> ListCategory:
        return ListCategory(
            list_id=row["list_id"], category_id=row["category_id"],
            priority=Priority(row["priority"]), name=row["name"], id=row["id"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _ls(row: sqlite3.Row) -> ListSubcategory:
        return ListSubcategory(
            list_category_id=row["list_category_id"], subcategory_id=row["subcategory_id"],
            priority=Priority(row["priority"]), name=row["name"], id=row["id"],
            updated_at=row["updated_at"],
        )

    def list_categories(self, list_id: str) -> list[ListCategory]:
        rows = self.conn.execute(
            "SELECT lc.*, c.name FROM list_category lc "
            "JOIN catalog_category c ON c.id = lc.category_id "
            "WHERE lc.list_id = ? ORDER BY lc.priority, c.name COLLATE NOCASE",
            (list_id,),
        )
        return [self._lc(r) for r in rows]

    def get_list_category(self, list_category_id: str) -> Optional[ListCategory]:
        row = self.conn.execute(
            "SELECT lc.*, c.name FROM list_category lc "
            "JOIN catalog_category c ON c.id = lc.category_id WHERE lc.id = ?",
            (list_category_id,),
        ).fetchone()
        return self._lc(row) if row else None

    def add_list_category(
        self, list_id: str, category_id: str, priority: object = Priority.MUST_HAVE
    ) -> ListCategory:
        if not self.get_list(list_id):
            raise ValidationError("List not found.")
        cat = self.get_catalog_category(category_id)
        if not cat:
            raise ValidationError("Category not found.")
        exists = self.conn.execute(
            "SELECT 1 FROM list_category WHERE list_id = ? AND category_id = ?",
            (list_id, category_id),
        ).fetchone()
        if exists:
            raise ValidationError(f"'{cat.name}' is already in this list.")
        lc = ListCategory(list_id=list_id, category_id=category_id,
                          priority=_priority(priority), name=cat.name)
        with self.conn:
            self.conn.execute(
                "INSERT INTO list_category(id, list_id, category_id, priority, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (lc.id, lc.list_id, lc.category_id, int(lc.priority), lc.updated_at),
            )
        return lc

    def set_list_category_priority(self, list_category_id: str, priority: object) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE list_category SET priority = ?, updated_at = ? WHERE id = ?",
                (int(_priority(priority)), utc_now(), list_category_id),
            )

    def remove_list_category(self, list_category_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM list_category WHERE id = ?", (list_category_id,))

    def list_subcategories(self, list_category_id: str) -> list[ListSubcategory]:
        rows = self.conn.execute(
            "SELECT ls.*, s.name FROM list_subcategory ls "
            "JOIN catalog_subcategory s ON s.id = ls.subcategory_id "
            "WHERE ls.list_category_id = ? ORDER BY ls.priority, s.name COLLATE NOCASE",
            (list_category_id,),
        )
        return [self._ls(r) for r in rows]

    def add_list_subcategory(
        self, list_category_id: str, subcategory_id: str, priority: object = Priority.MUST_HAVE
    ) -> ListSubcategory:
        lc = self.get_list_category(list_category_id)
        if not lc:
            raise ValidationError("List category not found.")
        sub = self.get_catalog_subcategory(subcategory_id)
        if not sub or sub.category_id != lc.category_id:
            raise ValidationError("Sub-category does not belong to this category.")
        exists = self.conn.execute(
            "SELECT 1 FROM list_subcategory WHERE list_category_id = ? AND subcategory_id = ?",
            (list_category_id, subcategory_id),
        ).fetchone()
        if exists:
            raise ValidationError(f"'{sub.name}' is already in this category.")
        ls = ListSubcategory(list_category_id=list_category_id, subcategory_id=subcategory_id,
                             priority=_priority(priority), name=sub.name)
        with self.conn:
            self.conn.execute(
                "INSERT INTO list_subcategory(id, list_category_id, subcategory_id, priority, "
                "updated_at) VALUES (?, ?, ?, ?, ?)",
                (ls.id, ls.list_category_id, ls.subcategory_id, int(ls.priority), ls.updated_at),
            )
        return ls

    def set_list_subcategory_priority(self, list_subcategory_id: str, priority: object) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE list_subcategory SET priority = ?, updated_at = ? WHERE id = ?",
                (int(_priority(priority)), utc_now(), list_subcategory_id),
            )

    def remove_list_subcategory(self, list_subcategory_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM list_subcategory WHERE id = ?", (list_subcategory_id,))

    # ----------------------------------------------------------------- items
    @staticmethod
    def _item(row: sqlite3.Row) -> Item:
        return Item(
            list_category_id=row["list_category_id"], name=row["name"],
            priority=Priority(row["priority"]), cost=row["cost"], status=Status(row["status"]),
            list_subcategory_id=row["list_subcategory_id"], id=row["id"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def items_for_list_category(self, list_category_id: str) -> list[Item]:
        rows = self.conn.execute(
            "SELECT * FROM item WHERE list_category_id = ? "
            "ORDER BY priority, created_at",
            (list_category_id,),
        )
        return [self._item(r) for r in rows]

    def items_for_list(self, list_id: str) -> list[Item]:
        rows = self.conn.execute(
            "SELECT i.* FROM item i JOIN list_category lc ON lc.id = i.list_category_id "
            "WHERE lc.list_id = ? ORDER BY i.priority, i.created_at",
            (list_id,),
        )
        return [self._item(r) for r in rows]

    def get_item(self, item_id: str) -> Optional[Item]:
        row = self.conn.execute("SELECT * FROM item WHERE id = ?", (item_id,)).fetchone()
        return self._item(row) if row else None

    def add_item(
        self,
        list_category_id: str,
        name: str,
        priority: object = Priority.MUST_HAVE,
        cost: object = None,
        list_subcategory_id: Optional[str] = None,
    ) -> Item:
        if not self.get_list_category(list_category_id):
            raise ValidationError("List category not found.")
        if list_subcategory_id:
            self._check_subcategory_parent(list_category_id, list_subcategory_id)
        item = Item(
            list_category_id=list_category_id, name=clean_name(name, "Item name"),
            priority=_priority(priority), cost=clean_cost(cost),
            list_subcategory_id=list_subcategory_id or None,
        )
        with self.conn:
            self.conn.execute(
                "INSERT INTO item(id, list_category_id, list_subcategory_id, name, priority, "
                "cost, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.id, item.list_category_id, item.list_subcategory_id, item.name,
                 int(item.priority), item.cost, item.status.value, item.created_at,
                 item.updated_at),
            )
        return item

    def _check_subcategory_parent(self, list_category_id: str, list_subcategory_id: str) -> None:
        row = self.conn.execute(
            "SELECT list_category_id FROM list_subcategory WHERE id = ?", (list_subcategory_id,)
        ).fetchone()
        if not row or row["list_category_id"] != list_category_id:
            raise ValidationError("Sub-category does not belong to this category.")

    def update_item(
        self, item_id: str, name: object, priority: object, cost: object
    ) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE item SET name = ?, priority = ?, cost = ?, updated_at = ? WHERE id = ?",
                (clean_name(name, "Item name"), int(_priority(priority)), clean_cost(cost),
                 utc_now(), item_id),
            )

    def set_item_status(self, item_id: str, status: object) -> None:
        try:
            value = Status(status).value
        except ValueError as exc:
            raise ValidationError(f"Unknown status {status!r}.") from exc
        with self.conn:
            self.conn.execute(
                "UPDATE item SET status = ?, updated_at = ? WHERE id = ?",
                (value, utc_now(), item_id),
            )

    def delete_item(self, item_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM item WHERE id = ?", (item_id,))

    def delete_items(self, item_ids: Iterable[str]) -> None:
        with self.conn:
            self.conn.executemany("DELETE FROM item WHERE id = ?", [(i,) for i in item_ids])
