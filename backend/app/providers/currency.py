from decimal import Decimal

from app.schemas.common import money


REFERENCE_TO_INR = {
    "INR": Decimal("1"),
    "USD": Decimal("84.00"),
    "EUR": Decimal("91.00"),
    "GBP": Decimal("109.00"),
    "LKR": Decimal("0.28"),
    "JPY": Decimal("0.56"),
    "AUD": Decimal("55.00"),
}


async def get_exchange_rate(source: str, target: str) -> Decimal:
    source = source.upper()
    target = target.upper()
    if source == target:
        return Decimal("1")
    if source not in REFERENCE_TO_INR or target not in REFERENCE_TO_INR:
        return Decimal("1")
    return (REFERENCE_TO_INR[source] / REFERENCE_TO_INR[target]).quantize(Decimal("0.000001"))


def convert(amount: Decimal, rate: Decimal) -> Decimal:
    return money(amount * rate)

