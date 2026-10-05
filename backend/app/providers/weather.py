import asyncio
import hashlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.place import WeatherAnalysis

OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"


def _score(value: Decimal) -> Decimal:
    return min(Decimal("10"), max(Decimal("0"), value)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def _analysis(
    *,
    temperature: Decimal,
    rain_probability: int,
    humidity: int,
    wind: Decimal,
    summary: str | None = None,
) -> WeatherAnalysis:
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
    return WeatherAnalysis(
        score=overall,
        rating=rating,
        summary=summary
        or {
            "EXCELLENT": "Comfortable conditions are likely across most of the trip.",
            "GOOD": "Generally pleasant conditions, with a chance of passing rain.",
            "MIXED": "Plan flexible indoor alternatives around rain and warmer hours.",
        }[rating],
        temperature_c=temperature,
        rain_probability=rain_probability,
        humidity=humidity,
        wind_kph=wind,
    )


async def _local_weather(destination: str, start_date: date) -> WeatherAnalysis:
    await asyncio.sleep(0)
    seed = int(hashlib.sha256(destination.lower().encode()).hexdigest()[:8], 16)
    seasonal = abs(7 - start_date.month)
    return _analysis(
        temperature=Decimal(20 + seed % 12 - min(seasonal, 4)),
        rain_probability=int(22 + (seed + start_date.month * 7) % 54),
        humidity=int(50 + (seed // 3) % 36),
        wind=Decimal(6 + (seed // 11) % 17),
    )


async def _openweather(
    destination: str, api_key: str, client: httpx.AsyncClient | None
) -> WeatherAnalysis:
    owns_client = client is None
    active_client = client or httpx.AsyncClient()
    try:
        response = await active_client.get(
            OPENWEATHER_CURRENT_URL,
            params={"q": destination, "appid": api_key, "units": "metric"},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
        temperature = Decimal(str(payload["main"]["temp"])).quantize(Decimal("0.1"))
        humidity = int(payload["main"]["humidity"])
        wind = (Decimal(str(payload.get("wind", {}).get("speed", 0))) * Decimal("3.6")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        condition = payload["weather"][0]
        raining = condition.get("main") in {"Thunderstorm", "Drizzle", "Rain", "Snow"}
        raining = raining or "rain" in payload or "snow" in payload
        place_name = str(payload.get("name") or destination)
        description = str(condition["description"])
        summary = (
            f"Current conditions in {place_name}: {description}, {temperature}°C, "
            f"{humidity}% humidity, wind {wind} km/h."
        )
        return _analysis(
            temperature=temperature,
            rain_probability=100 if raining else 0,
            humidity=humidity,
            wind=wind,
            summary=summary,
        )
    finally:
        if owns_client:
            await active_client.aclose()


async def get_weather(
    destination: str, start_date: date, *, client: httpx.AsyncClient | None = None
) -> WeatherAnalysis:
    """Return live current conditions when configured, or stable seasonal fallback data."""
    settings = get_settings()
    if settings.weather_provider.lower() == "openweather" and settings.openweather_api_key:
        try:
            return await _openweather(destination, settings.openweather_api_key, client)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError):
            pass
    return await _local_weather(destination, start_date)
