"""SQLite connection and schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

_MIGRATIONS: list[str] = [
    # v1 - initial schema
    """
    CREATE TABLE meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE catalog_category (
        id         TEXT PRIMARY KEY,
        name       TEXT NOT NULL COLLATE NOCASE UNIQUE,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE catalog_subcategory (
        id          TEXT PRIMARY KEY,
        category_id TEXT NOT NULL REFERENCES catalog_category(id) ON DELETE CASCADE,
        name        TEXT NOT NULL COLLATE NOCASE,
        updated_at  TEXT NOT NULL,
        UNIQUE (category_id, name)
    );
    CREATE TABLE shopping_list (
        id         TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        currency   TEXT NOT NULL DEFAULT 'INR',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE list_category (
        id          TEXT PRIMARY KEY,
        list_id     TEXT NOT NULL REFERENCES shopping_list(id) ON DELETE CASCADE,
        category_id TEXT NOT NULL REFERENCES catalog_category(id) ON DELETE RESTRICT,
        priority    INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 3),
        updated_at  TEXT NOT NULL,
        UNIQUE (list_id, category_id)
    );
    CREATE TABLE list_subcategory (
        id               TEXT PRIMARY KEY,
        list_category_id TEXT NOT NULL REFERENCES list_category(id) ON DELETE CASCADE,
        subcategory_id   TEXT NOT NULL REFERENCES catalog_subcategory(id) ON DELETE RESTRICT,
        priority         INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 3),
        updated_at       TEXT NOT NULL,
        UNIQUE (list_category_id, subcategory_id)
    );
    CREATE TABLE item (
        id                  TEXT PRIMARY KEY,
        list_category_id    TEXT NOT NULL REFERENCES list_category(id) ON DELETE CASCADE,
        list_subcategory_id TEXT REFERENCES list_subcategory(id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        priority            INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 3),
        cost                REAL CHECK (cost IS NULL OR cost >= 0),
        status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'bought', 'not_available')),
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    );
    CREATE INDEX idx_list_category_list ON list_category(list_id);
    CREATE INDEX idx_list_subcategory_parent ON list_subcategory(list_category_id);
    CREATE INDEX idx_item_category ON item(list_category_id);
    CREATE INDEX idx_item_subcategory ON item(list_subcategory_id);
    """,
]

SCHEMA_VERSION = len(_MIGRATIONS)


def connect(path: Union[str, Path]) -> sqlite3.Connection:
    """Open (and migrate) the database. Use ``":memory:"`` for tests."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema v{current} is newer than this app (v{SCHEMA_VERSION})."
        )
    for version in range(current, SCHEMA_VERSION):
        with conn:
            conn.executescript("BEGIN;" + _MIGRATIONS[version])
            conn.execute(f"PRAGMA user_version = {version + 1}")
