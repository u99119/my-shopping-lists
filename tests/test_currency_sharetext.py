import pytest

from msl.core.currency import Rates, format_money
from msl.core.models import Status
from msl.core.repository import ValidationError
from msl.core.sharetext import format_list_text
from msl.core.viewmodel import build_list_view


def test_format_money():
    assert format_money(1234.5) == "₹1,234.50"
    assert format_money(1500, "JPY") == "¥1,500"
    assert format_money(10, "CHF") == "10.00 CHF"
    assert format_money(None) == ""


def test_rates_convert_and_persist(repo):
    rates = Rates(repo)
    assert rates.convert(100, "INR", "INR") == 100
    rates.set_rate("jpy", "0.6")
    assert Rates(repo).all()["JPY"] == 0.6
    assert rates.convert(1000, "JPY", "INR") == 600.0
    assert rates.convert(600, "INR", "JPY") == 1000.0


@pytest.mark.parametrize("code,value", [("INR", 2), ("JPY", 0), ("JPY", "x"), ("XX", 1)])
def test_rates_reject(repo, code, value):
    with pytest.raises(ValidationError):
        Rates(repo).set_rate(code, value)


def test_convert_unknown_currency(repo):
    with pytest.raises(ValidationError):
        Rates(repo).convert(1, "XYZ", "INR")


def test_corrupt_rates_fall_back_to_defaults(repo):
    repo.set_meta("fx_rates_inr", "not json")
    assert Rates(repo).all()["INR"] == 1.0


def test_share_text(repo, shop):
    sl, _, _, items = shop
    repo.set_item_status(items["melonpan"].id, Status.BOUGHT)
    repo.set_item_status(items["mochi"].id, Status.NOT_AVAILABLE)
    text = format_list_text(build_list_view(repo, sl.id))
    assert text.startswith("🛒 Tokyo\n")
    assert "*Food*" in text
    assert "  ☐ Ramen — ₹900.00" in text
    assert "  ▸ Bakeries" in text
    assert "    ☑ Melonpan — ₹150.00" in text
    assert "✗ Mochi (can avoid) [not available]" in text
    assert "Items: 4 · bought 1 · remaining 2" in text


def test_share_text_pending_only(repo, shop):
    sl, _, _, items = shop
    repo.set_item_status(items["melonpan"].id, Status.BOUGHT)
    text = format_list_text(build_list_view(repo, sl.id), include_closed=False)
    assert "Melonpan" not in text
    assert "Croissant" in text
