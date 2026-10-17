from msl.core.models import Status
from msl.core.viewmodel import build_list_view, list_summary


def test_list_view_structure_and_totals(repo, shop):
    sl, _, _, items = shop
    repo.set_item_status(items["melonpan"].id, Status.BOUGHT)
    repo.set_item_status(items["croissant"].id, Status.NOT_AVAILABLE)
    view = build_list_view(repo, sl.id)
    (cv,) = view.categories
    assert [i.name for i in cv.direct_items] == ["Ramen", "Mochi"]
    assert [i.name for i in cv.subcategories[0].items] == ["Melonpan", "Croissant"]
    t = view.totals
    assert (t.total, t.bought, t.not_available, t.remaining) == (4, 1, 1, 2)
    assert t.cost_total == 1050.0  # not-available excluded
    assert t.cost_remaining == 900.0
    assert list_summary(repo, sl.id) == t


def test_collapsed_rows_show_only_top_priority_pending(repo, shop):
    sl, _, _, items = shop
    cv = build_list_view(repo, sl.id).categories[0]
    assert [(s, i.name) for s, i in cv.collapsed_rows] == [("Bakeries", "Melonpan"), (None, "Ramen")]

    repo.set_item_status(items["melonpan"].id, Status.BOUGHT)
    repo.set_item_status(items["ramen"].id, Status.BOUGHT)
    cv = build_list_view(repo, sl.id).categories[0]
    assert [(s, i.name) for s, i in cv.collapsed_rows] == [
        ("Bakeries", "Croissant"), (None, "Mochi"),
    ]


def test_collapsed_rows_include_ties(repo, shop):
    sl, lc, _, _ = shop
    repo.add_item(lc.id, "Sushi", 1, 1200)
    cv = build_list_view(repo, sl.id).categories[0]
    assert [i.name for s, i in cv.collapsed_rows if s is None] == ["Ramen", "Sushi"]


def test_categories_sorted_by_priority(repo, shop):
    sl, *_ = shop
    clothes = repo.find_catalog_category("Clothes")
    repo.add_list_category(sl.id, clothes.id, 1)
    toys = repo.find_catalog_category("Toys")
    repo.add_list_category(sl.id, toys.id, 3)
    names = [cv.category.name for cv in build_list_view(repo, sl.id).categories]
    assert names == ["Clothes", "Food", "Toys"]


def test_missing_list_returns_none(repo):
    assert build_list_view(repo, "nope") is None
