"""Decimal helpers provide small independent symbols for exploration."""

from decimal import Decimal, ROUND_HALF_UP


def round_money(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_cents(value: str) -> int:
    return int(round_money(value) * 100)


def from_cents(value: int) -> str:
    return format(Decimal(value) / 100, ".2f")
