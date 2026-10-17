import json

import pytest

from msl.core.db import connect
from msl.core.models import Status
from msl.core.repository import Repository, ValidationError
from msl.core.seed import seed_catalog
from msl.core.transfer import FORMAT, export_data, export_json, import_json, merge_data


@pytest.fixture
def other() -> Repository:
    r = Repository(connect(":memory:"))
    seed_catalog(r)
    return r


def _count(repo, table):
    return repo.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_round_trip_into_fresh_device(repo, shop, other):
    sl, *_ = shop
    report = import_json(other, export_json(repo))
    # 1 list + 1 list_category + 1 list_subcategory + 4 items; catalog matched by name
    assert report.added == 7
    assert report.updated == 0
    assert other.get_list(sl.id).name == "Tokyo"
    assert len(other.items_for_list(sl.id)) == 4
    assert _count(other, "catalog_category") == _count(repo, "catalog_category")


def test_import_is_idempotent(repo, shop, other):
    import_json(other, export_json(repo))
    report = import_json(other, export_json(repo))
    assert (report.added, report.updated) == (0, 0)


def test_newer_wins_both_directions(repo, shop, other):
    _, _, _, items = shop
    import_json(other, export_json(repo))
    repo.set_item_status(items["ramen"].id, Status.BOUGHT)
    other.update_item(items["mochi"].id, "Daifuku", 3, 300)

    report = import_json(other, export_json(repo))
    assert report.updated == 1
    assert other.get_item(items["ramen"].id).status is Status.BOUGHT
    assert other.get_item(items["mochi"].id).name == "Daifuku"  # local newer kept

    import_json(repo, export_json(other))
    assert repo.get_item(items["mochi"].id).name == "Daifuku"


def test_import_never_deletes(repo, shop, other):
    _, _, _, items = shop
    import_json(other, export_json(repo))
    repo.delete_item(items["ramen"].id)
    import_json(other, export_json(repo))
    assert other.get_item(items["ramen"].id) is not None


def test_user_added_catalog_merged_by_name(repo, other):
    a = repo.add_catalog_category("Books")
    b = other.add_catalog_category("books")
    sl = repo.create_list("L")
    lc = repo.add_list_category(sl.id, a.id)
    repo.add_item(lc.id, "Manga")
    import_json(other, export_json(repo))
    assert other.get_list_category(lc.id).category_id == b.id
    assert _count(other, "catalog_category") == _count(repo, "catalog_category")


def test_rename_clash_is_skipped(repo, other):
    a = repo.add_catalog_category("Books")
    import_json(other, export_json(repo))
    other.add_catalog_category("Comics")
    repo.rename_catalog_category(a.id, "Comics")
    report = import_json(other, export_json(repo))
    assert report.skipped == 1
    assert other.get_catalog_category(a.id).name == "Books"


@pytest.mark.parametrize("text", [
    "not json",
    json.dumps([]),
    json.dumps({"format": "other", "version": 1}),
    json.dumps({"format": FORMAT, "version": 0}),
    json.dumps({"format": FORMAT, "version": 99}),
    json.dumps({"format": FORMAT, "version": 1, "lists": {}}),
    json.dumps({"format": FORMAT, "version": 1, "lists": [{"id": "x"}]}),
])
def test_rejects_bad_files(other, text):
    with pytest.raises(ValidationError):
        import_json(other, text)


def test_bad_reference_rolls_back_everything(repo, shop, other):
    data = export_data(repo)
    data["items"][0]["list_category_id"] = "missing"
    with pytest.raises(ValidationError):
        merge_data(other, data)
    assert _count(other, "shopping_list") == 0
    assert _count(other, "item") == 0


def test_bad_status_rejected(repo, shop, other):
    data = export_data(repo)
    data["items"][0]["status"] = "lost"
    with pytest.raises(ValidationError):
        merge_data(other, data)
