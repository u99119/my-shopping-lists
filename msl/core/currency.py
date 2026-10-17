"""Offline currency formatting and conversion (INR base, last-known approximate rates)."""

from __future__ import annotations

import json
from typing import Optional

from .repository import Repository, ValidationError, clean_currency

BASE = "INR"
RATES_META_KEY = "fx_rates_inr"

# Approximate units of INR per 1 unit of currency. Editable by the user; used offline.
DEFAULT_RATES: dict[str, float] = {
    "INR": 1.0,
    "USD": 88.0,
    "EUR": 102.0,
    "GBP": 118.0,
    "JPY": 0.58,
    "AED": 24.0,
    "SGD": 68.0,
    "THB": 2.7,
}

SYMBOLS: dict[str, str] = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
}


def format_money(amount: Optional[float], currency: str = BASE) -> str:
    if amount is None:
        return ""
    symbol = SYMBOLS.get(currency.upper())
    decimals = 0 if currency.upper() == "JPY" else 2
    text = f"{amount:,.{decimals}f}"
    return f"{symbol}{text}" if symbol else f"{text} {currency.upper()}"


class Rates:
    """Per-device table of INR rates, persisted in the ``meta`` table."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def all(self) -> dict[str, float]:
        rates = dict(DEFAULT_RATES)
        raw = self.repo.get_meta(RATES_META_KEY)
        if raw:
            try:
                stored = json.loads(raw)
                rates.update({k: float(v) for k, v in stored.items() if float(v) > 0})
            except (ValueError, TypeError, AttributeError):
                pass
        return rates

    def set_rate(self, currency: str, inr_per_unit: object) -> None:
        code = clean_currency(currency)
        if code == BASE:
            raise ValidationError("INR rate is fixed at 1.")
        try:
            value = float(str(inr_per_unit).strip())
        except ValueError as exc:
            raise ValidationError("Rate must be a number.") from exc
        if not value > 0 or value == float("inf"):
            raise ValidationError("Rate must be greater than zero.")
        rates = self.all()
        rates[code] = value
        rates.pop(BASE, None)
        self.repo.set_meta(RATES_META_KEY, json.dumps(rates, sort_keys=True))

    def convert(self, amount: float, src: str, dst: str) -> float:
        src, dst = src.upper(), dst.upper()
        if src == dst:
            return amount
        rates = self.all()
        if src not in rates or dst not in rates:
            raise ValidationError(f"No rate for {src if src not in rates else dst}.")
        return round(amount * rates[src] / rates[dst], 2)
