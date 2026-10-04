from decimal import ROUND_HALF_UP, Decimal

MONEY_STEP = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
