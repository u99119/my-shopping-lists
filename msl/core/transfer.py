"""Full-data export and merge-import (device to device, no cloud).

Merge rules: records match by id, else by natural key (catalog names, list/category pairs);
the newer ``updated_at`` wins; nothing is ever deleted by an import; the whole import is atomic.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Optional

from .. import __version__
from .models import Status, utc_now
from .repository import (
    Repository, ValidationError, _priority, clean_cost, clean_currency, clean_name,
)

FORMAT = "my-shopping-lists"
FORMAT_VERSION = 1

_TABLES: list[tuple[str, str, tuple[str, ...]]] = [
    ("catalog_categories", "catalog_category", ("id", "name", "updated_at")),
    ("catalog_subcategories", "catalog_subcategory", ("id", "category_id", "name", "updated_at")),
    ("lists", "shopping_list", ("id", "name", "currency", "created_at", "updated_at")),
    ("list_categories", "list_category",
     ("id", "list_id", "category_id", "priority", "updated_at")),
    ("list_subcategories", "list_subcategory",
     ("id", "list_category_id", "subcategory_id", "priority", "updated_at")),
    ("items", "item", ("id", "list_category_id", "list_subcategory_id", "name", "priority",
                       "cost", "status", "created_at", "updated_at")),
]
_PARENTS: dict[str, dict[str, str]] = {
    "catalog_subcategory": {"category_id": "catalog_category"},
    "list_category": {"list_id": "shopping_list", "category_id": "catalog_category"},
    "list_subcategory": {"list_category_id": "list_category",
                         "subcategory_id": "catalog_subcategory"},
    "item": {"list_category_id": "list_category", "list_subcategory_id": "list_subcategory"},
}
_NATURAL_KEYS: dict[str, tuple[str, ...]] = {
    "catalog_category": ("name",),
    "catalog_subcategory": ("category_id", "name"),
    "list_category": ("list_id", "category_id"),
    "list_subcategory": ("list_category_id", "subcategory_id"),
}
_OPTIONAL = {"list_subcategory_id", "cost"}


@dataclass
class MergeReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0

    def __str__(self) -> str:
        text = f"{self.added} added, {self.updated} updated, {self.unchanged} unchanged"
        return text + (f", {self.skipped} skipped (name clash)" if self.skipped else "")


def export_data(repo: Repository) -> dict[str, Any]:
    data: dict[str, Any] = {
        "format": FORMAT, "version": FORMAT_VERSION,
        "app_version": __version__, "exported_at": utc_now(),
    }
    for key, table, cols in _TABLES:
        rows = repo.conn.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY id")
        data[key] = [dict(r) for r in rows]
    return data


def export_json(repo: Repository) -> str:
    return json.dumps(export_data(repo), ensure_ascii=False, indent=1)


def import_json(repo: Repository, text: str) -> MergeReport:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValidationError("File is not a valid My Shopping Lists export.") from exc
    return merge_data(repo, data)


def merge_data(repo: Repository, data: Any) -> MergeReport:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValidationError("File is not a valid My Shopping Lists export.")
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise ValidationError("Export file has an unknown version.")
    if version > FORMAT_VERSION:
        raise ValidationError("Export was made by a newer app version; please update the app.")
    records = {key: _records(data, key, cols) for key, _, cols in _TABLES}
    merger = _Merger(repo.conn)
    try:
        with repo.conn:
            for key, table, cols in _TABLES:
                for rec in records[key]:
                    merger.merge(table, cols, rec)
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Export file is inconsistent: {exc}") from exc
    return merger.report


def _records(data: dict, key: str, cols: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = data.get(key, [])
    if not isinstance(rows, list):
        raise ValidationError(f"Malformed section '{key}' in export file.")
    out = []
    for row in rows:
        if not isinstance(row, dict) or any(c not in row for c in cols if c not in _OPTIONAL):
            raise ValidationError(f"Malformed record in '{key}'.")
        out.append(_clean({c: row.get(c) for c in cols}))
    return out


def _clean(rec: dict[str, Any]) -> dict[str, Any]:
    for col in ("id", "created_at", "updated_at"):
        if col in rec and not (isinstance(rec[col], str) and rec[col]):
            raise ValidationError(f"Malformed '{col}' in export file.")
    if "name" in rec:
        rec["name"] = clean_name(rec["name"])
    if "currency" in rec:
        rec["currency"] = clean_currency(rec["currency"])
    if "priority" in rec:
        rec["priority"] = int(_priority(rec["priority"]))
    if "cost" in rec:
        rec["cost"] = clean_cost(rec["cost"])
    if "status" in rec:
        try:
            rec["status"] = Status(rec["status"]).value
        except ValueError as exc:
            raise ValidationError(f"Unknown status {rec['status']!r}.") from exc
    return rec


class _Merger:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.report = MergeReport()
        self.ids: dict[str, dict[str, str]] = {table: {} for _, table, _ in _TABLES}

    def _map(self, table: str, ref: Optional[str], col: str) -> Optional[str]:
        if ref is None and col in _OPTIONAL:
            return None
        local = self.ids[table].get(ref) if isinstance(ref, str) else None
        if local is None:
            raise ValidationError(f"Export file references a missing {table.replace('_', ' ')}.")
        return local

    def merge(self, table: str, cols: tuple[str, ...], rec: dict[str, Any]) -> None:
        incoming_id = rec["id"]
        for col, parent in _PARENTS.get(table, {}).items():
            rec[col] = self._map(parent, rec[col], col)
        if table == "item" and rec["list_subcategory_id"]:
            owner = self.conn.execute(
                "SELECT list_category_id FROM list_subcategory WHERE id = ?",
                (rec["list_subcategory_id"],),
            ).fetchone()
            if not owner or owner[0] != rec["list_category_id"]:
                raise ValidationError("Export file has an item under the wrong sub-category.")

        local = self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (incoming_id,)).fetchone()
        if local is None and table in _NATURAL_KEYS:
            keys = _NATURAL_KEYS[table]
            where = " AND ".join(f"{k} = ?" for k in keys)
            local = self.conn.execute(
                f"SELECT * FROM {table} WHERE {where}", [rec[k] for k in keys]
            ).fetchone()

        if local is None:
            self.conn.execute(
                f"INSERT INTO {table}({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [rec[c] for c in cols],
            )
            self.ids[table][incoming_id] = incoming_id
            self.report.added += 1
            return

        self.ids[table][incoming_id] = local["id"]
        if rec["updated_at"] <= local["updated_at"]:
            self.report.unchanged += 1
            return
        update_cols = [c for c in cols if c not in ("id", "created_at")]
        try:
            self.conn.execute(
                f"UPDATE {table} SET {', '.join(f'{c} = ?' for c in update_cols)} WHERE id = ?",
                [*(rec[c] for c in update_cols), local["id"]],
            )
        except sqlite3.IntegrityError:
            self.report.skipped += 1
            return
        self.report.updated += 1
