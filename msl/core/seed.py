"""Preloaded catalog (categories -> sub-categories)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import Repository

DEFAULT_CATALOG: dict[str, list[str]] = {
    "Stationary": ["Fountain pen", "Notebooks"],
    "Alcohol": [],
    "Clothes": ["Socks"],
    "Souvenirs": [],
    "Kitchen": [],
    "Makeup": [],
    "Food": ["Street Food", "Bakeries"],
    "Toys": [],
    "Electronics": [],
    "Perfumes": [],
}

_SEEDED_KEY = "catalog_seeded"


def seed_catalog(repo: "Repository") -> bool:
    """Load the default catalog once (first run). Returns True if seeded now."""
    if repo.get_meta(_SEEDED_KEY) == "1":
        return False
    for category_name, sub_names in DEFAULT_CATALOG.items():
        category = repo.get_or_create_catalog_category(category_name)
        for sub_name in sub_names:
            repo.get_or_create_catalog_subcategory(category.id, sub_name)
    repo.set_meta(_SEEDED_KEY, "1")
    return True
