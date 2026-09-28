from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANT = Decimal("0.01")


def money(value: float | int | str | Decimal | None) -> Decimal:
    if value is None:
        value = 0
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def money_float(value: float | int | str | Decimal | None) -> float:
    return float(money(value))


def format_neuro(value: float | int | str | Decimal | None) -> str:
    return f"{money(value):.2f}"


def format_signed_neuro(value: float | int | str | Decimal | None) -> str:
    amount = money(value)
    sign = "+" if amount >= 0 else ""
    return f"{sign}{amount:.2f}"
