import pytest

from msl.core.db import connect
from msl.core.repository import Repository
from msl.core.seed import seed_catalog


@pytest.fixture
def repo() -> Repository:
    r = Repository(connect(":memory:"))
    seed_catalog(r)
    return r


@pytest.fixture
def food(repo):
    return repo.find_catalog_category("Food")


@pytest.fixture
def shop(repo, food):
    """A list with Food (+ Bakeries sub-category) and a few items."""
    sl = repo.create_list("Tokyo")
    lc = repo.add_list_category(sl.id, food.id)
    bakeries = repo.find_catalog_subcategory(food.id, "Bakeries")
    ls = repo.add_list_subcategory(lc.id, bakeries.id)
    items = {
        "melonpan": repo.add_item(lc.id, "Melonpan", 1, 150, ls.id),
        "croissant": repo.add_item(lc.id, "Croissant", 2, 200, ls.id),
        "ramen": repo.add_item(lc.id, "Ramen", 1, 900),
        "mochi": repo.add_item(lc.id, "Mochi", 3, None),
    }
    return sl, lc, ls, items
