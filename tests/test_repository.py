from datetime import date

import pytest

from msl.core.db import SCHEMA_VERSION, connect
from msl.core.models import Priority, Status
from msl.core.repository import InUseError, ValidationError, clean_cost, clean_name
from msl.core.seed import DEFAULT_CATALOG, seed_catalog


def test_schema_version_and_reopen(tmp_path):
    path = tmp_path / "db" / "msl.sqlite"
    conn = connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()
    assert connect(path).execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_seed_runs_once(repo):
    assert len(repo.list_catalog_categories()) == len(DEFAULT_CATALOG)
    assert seed_catalog(repo) is False


@pytest.mark.parametrize("raw,expected", [("  Pen  ", "Pen"), ("a   b", "a b")])
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "x" * 101])
def test_clean_name_rejects(raw):
    with pytest.raises(ValidationError):
        clean_name(raw)


@pytest.mark.parametrize("raw,expected", [(None, None), ("", None), ("1,200.456", 1200.46), (0, 0.0)])
def test_clean_cost(raw, expected):
    assert clean_cost(raw) == expected


@pytest.mark.parametrize("raw", ["abc", -1, "nan", "inf"])
def test_clean_cost_rejects(raw):
    with pytest.raises(ValidationError):
        clean_cost(raw)


def test_catalog_crud_and_case_insensitive_unique(repo):
    cat = repo.add_catalog_category("Books")
    with pytest.raises(ValidationError):
        repo.add_catalog_category("books")
    repo.rename_catalog_category(cat.id, "Manga")
    assert repo.get_catalog_category(cat.id).name == "Manga"
    sub = repo.add_catalog_subcategory(cat.id, "Shonen")
    with pytest.raises(ValidationError):
        repo.add_catalog_subcategory(cat.id, "SHONEN")
    repo.rename_catalog_subcategory(sub.id, "Seinen")
    assert [s.name for s in repo.list_catalog_subcategories(cat.id)] == ["Seinen"]
    repo.delete_catalog_subcategory(sub.id)
    repo.delete_catalog_category(cat.id)
    assert repo.get_catalog_category(cat.id) is None


def test_catalog_delete_in_use(repo, shop, food):
    _, _, ls, _ = shop
    with pytest.raises(InUseError):
        repo.delete_catalog_category(food.id)
    with pytest.raises(InUseError):
        repo.delete_catalog_subcategory(ls.subcategory_id)


def test_default_list_names_are_unique(repo):
    today = date(2026, 10, 17)
    assert repo.default_list_name(today) == "SL_2026-10-17"
    repo.create_list("SL_2026-10-17")
    assert repo.default_list_name(today) == "SL_2026-10-17 (2)"


def test_list_rename_currency_delete(repo, shop):
    sl, *_ = shop
    repo.rename_list(sl.id, "Osaka")
    repo.set_list_currency(sl.id, "jpy")
    got = repo.get_list(sl.id)
    assert (got.name, got.currency) == ("Osaka", "JPY")
    with pytest.raises(ValidationError):
        repo.set_list_currency(sl.id, "YEN!")
    repo.delete_list(sl.id)
    assert repo.get_list(sl.id) is None
    assert repo.conn.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 0


def test_duplicate_list_resets_status(repo, shop):
    sl, _, _, items = shop
    repo.set_item_status(items["ramen"].id, Status.BOUGHT)
    repo.set_item_status(items["mochi"].id, "not_available")
    copy = repo.duplicate_list(sl.id)
    assert copy.name == "Tokyo copy"
    copied = repo.items_for_list(copy.id)
    assert len(copied) == 4
    assert {i.status for i in copied} == {Status.PENDING}
    assert {i.id for i in copied}.isdisjoint(i.id for i in items.values())
    sub_items = [i for i in copied if i.list_subcategory_id]
    assert len(sub_items) == 2
    assert repo.get_item(items["ramen"].id).status is Status.BOUGHT


def test_list_category_rules(repo, shop, food):
    sl, lc, _, _ = shop
    with pytest.raises(ValidationError):
        repo.add_list_category(sl.id, food.id)
    clothes = repo.find_catalog_category("Clothes")
    socks = repo.find_catalog_subcategory(clothes.id, "Socks")
    with pytest.raises(ValidationError):
        repo.add_list_subcategory(lc.id, socks.id)
    repo.set_list_category_priority(lc.id, 3)
    assert repo.get_list_category(lc.id).priority is Priority.CAN_AVOID
    with pytest.raises(ValidationError):
        repo.set_list_category_priority(lc.id, 4)


def test_item_crud_and_status(repo, shop):
    _, lc, ls, items = shop
    item_id = items["ramen"].id
    repo.update_item(item_id, "Tonkotsu ramen", 2, "1000")
    got = repo.get_item(item_id)
    assert (got.name, got.priority, got.cost) == ("Tonkotsu ramen", Priority.GOOD_TO_HAVE, 1000.0)
    repo.set_item_status(item_id, "bought")
    assert repo.get_item(item_id).status is Status.BOUGHT
    with pytest.raises(ValidationError):
        repo.set_item_status(item_id, "lost")
    repo.delete_items([item_id, items["mochi"].id])
    assert len(repo.items_for_list_category(lc.id)) == 2


def test_item_subcategory_must_match_category(repo, shop):
    sl, _, ls, _ = shop
    clothes = repo.add_list_category(sl.id, repo.find_catalog_category("Clothes").id)
    with pytest.raises(ValidationError):
        repo.add_item(clothes.id, "Hat", 1, None, ls.id)


def test_removing_subcategory_cascades_items(repo, shop):
    _, lc, ls, _ = shop
    repo.remove_list_subcategory(ls.id)
    assert [i.name for i in repo.items_for_list_category(lc.id)] == ["Ramen", "Mochi"]
