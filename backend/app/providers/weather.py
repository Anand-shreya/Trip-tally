import asyncio
import hashlib
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.place import WeatherAnalysis


def _score(value: Decimal) -> Decimal:
    return min(Decimal("10"), max(Decimal("0"), value)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


async def get_weather(destination: str, start_date: date) -> WeatherAnalysis:
    """Return stable seasonal weather when no live provider is configured."""
    await asyncio.sleep(0)
    seed = int(hashlib.sha256(destination.lower().encode()).hexdigest()[:8], 16)
    seasonal = abs(7 - start_date.month)
    temperature = Decimal(20 + seed % 12 - min(seasonal, 4))
    rain_probability = int(22 + (seed + start_date.month * 7) % 54)
    humidity = int(50 + (seed // 3) % 36)
    wind = Decimal(6 + (seed // 11) % 17)

    temperature_score = _score(Decimal("10") - abs(temperature - Decimal("24")) / 2)
    rain_score = _score(Decimal("10") - Decimal(rain_probability) / 10)
    humidity_score = _score(Decimal("10") - abs(Decimal(humidity) - Decimal("60")) / 8)
    wind_score = _score(Decimal("10") - max(Decimal("0"), wind - Decimal("12")) / 2)
    overall = _score(
        temperature_score * Decimal("0.30")
        + rain_score * Decimal("0.30")
        + humidity_score * Decimal("0.20")
        + wind_score * Decimal("0.20")
    )
    rating = "EXCELLENT" if overall >= 8 else "GOOD" if overall >= 6 else "MIXED"
    summary = {
        "EXCELLENT": "Comfortable conditions are likely across most of the trip.",
        "GOOD": "Generally pleasant conditions, with a chance of passing rain.",
        "MIXED": "Plan flexible indoor alternatives around rain and warmer hours.",
    }[rating]
    return WeatherAnalysis(
        score=overall,
        rating=rating,
        summary=summary,
        temperature_c=temperature,
        rain_probability=rain_probability,
        humidity=humidity,
        wind_kph=wind,
    )

