"""Domain models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Optional


def new_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> str:
    """ISO-8601 UTC timestamp with microseconds (lexicographically sortable)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Priority(IntEnum):
    MUST_HAVE = 1
    GOOD_TO_HAVE = 2
    CAN_AVOID = 3

    @property
    def label(self) -> str:
        return {1: "Must have", 2: "Good to have", 3: "Can avoid"}[int(self)]

    @classmethod
    def coerce(cls, value: object) -> "Priority":
        try:
            return cls(int(value))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Priority must be 1-3, got {value!r}") from exc


class Status(str, Enum):
    PENDING = "pending"
    BOUGHT = "bought"
    NOT_AVAILABLE = "not_available"

    @property
    def is_open(self) -> bool:
        return self is Status.PENDING


@dataclass
class CatalogCategory:
    name: str
    id: str = field(default_factory=new_id)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class CatalogSubcategory:
    category_id: str
    name: str
    id: str = field(default_factory=new_id)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class ShoppingList:
    name: str
    currency: str = "INR"
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class ListCategory:
    """A catalog category placed inside a shopping list."""

    list_id: str
    category_id: str
    priority: Priority = Priority.MUST_HAVE
    name: str = ""  # denormalised from catalog on read
    id: str = field(default_factory=new_id)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class ListSubcategory:
    """A catalog sub-category placed inside a list category."""

    list_category_id: str
    subcategory_id: str
    priority: Priority = Priority.MUST_HAVE
    name: str = ""  # denormalised from catalog on read
    id: str = field(default_factory=new_id)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class Item:
    list_category_id: str
    name: str
    priority: Priority = Priority.MUST_HAVE
    cost: Optional[float] = None
    status: Status = Status.PENDING
    list_subcategory_id: Optional[str] = None
    id: str = field(default_factory=new_id)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
