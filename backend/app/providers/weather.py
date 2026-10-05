import asyncio
import calendar
from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

import httpx

from app.core.config import get_settings
from app.schemas.planning import CurrentWeather, DailyWeather, ResolvedLocation, WeatherReport

OPENWEATHER_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_DAILY_FIELDS = (
    "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
    "precipitation_sum,weather_code,wind_speed_10m_max"
)


class WeatherProviderError(RuntimeError):
    pass


def _decimal(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _local_datetime(timestamp: object, offset_seconds: int) -> datetime:
    offset = timezone(timedelta(seconds=offset_seconds))
    return datetime.fromtimestamp(int(timestamp), tz=UTC).astimezone(offset)


def _date_range(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise WeatherProviderError("weather provider unavailable")
    return [start_date + timedelta(days=index) for index in range((end_date - start_date).days + 1)]


def _wmo_condition(code: int) -> str:
    if code == 0:
        return "Clear"
    if code in {1, 2}:
        return "Partly cloudy"
    if code == 3:
        return "Cloudy"
    if code in {45, 48}:
        return "Fog"
    if 51 <= code <= 57:
        return "Drizzle"
    if 61 <= code <= 67:
        return "Rain"
    if 71 <= code <= 77:
        return "Snow"
    if 80 <= code <= 82:
        return "Rain showers"
    if 85 <= code <= 86:
        return "Snow showers"
    if 95 <= code <= 99:
        return "Thunderstorm"
    return "Unknown"


def _parse_current(payload: dict, offset_seconds: int) -> CurrentWeather:
    condition = payload["weather"][0]
    main = payload["main"]
    wind = payload["wind"]
    system = payload["sys"]
    rain = payload.get("rain") or {}
    snow = payload.get("snow") or {}
    return CurrentWeather(
        observed_at=_local_datetime(payload["dt"], offset_seconds),
        condition=str(condition["main"]),
        description=str(condition["description"]),
        temperature_c=_decimal(main["temp"]),
        feels_like_c=_decimal(main["feels_like"]),
        minimum_c=_decimal(main["temp_min"]),
        maximum_c=_decimal(main["temp_max"]),
        humidity_percent=int(main["humidity"]),
        pressure_hpa=int(main["pressure"]),
        visibility_m=int(payload["visibility"]),
        cloud_percent=int(payload["clouds"]["all"]),
        wind_speed_kph=_decimal(Decimal(str(wind["speed"])) * Decimal("3.6")),
        wind_direction_degrees=int(wind.get("deg", 0)),
        rain_mm_1h=_decimal(rain["1h"]) if "1h" in rain else None,
        snow_mm_1h=_decimal(snow["1h"]) if "1h" in snow else None,
        sunrise_at=_local_datetime(system["sunrise"], offset_seconds),
        sunset_at=_local_datetime(system["sunset"], offset_seconds),
    )


def _aggregate_forecast(
    payload: dict, requested_dates: set[date], offset_seconds: int
) -> dict[date, DailyWeather]:
    grouped: dict[date, list[tuple[datetime, dict]]] = {}
    for sample in payload["list"]:
        local_time = _local_datetime(sample["dt"], offset_seconds)
        if local_time.date() in requested_dates:
            grouped.setdefault(local_time.date(), []).append((local_time, sample))

    rows: dict[date, DailyWeather] = {}
    for requested_date, samples in grouped.items():
        representative = min(
            samples,
            key=lambda item: abs(item[0].hour * 60 + item[0].minute - 12 * 60),
        )[1]
        conditions = [str(sample[1]["weather"][0]["main"]) for sample in samples]
        dominant = Counter(conditions).most_common(1)[0][0]
        humidity = round(
            sum(int(sample[1]["main"]["humidity"]) for sample in samples) / len(samples)
        )
        rows[requested_date] = DailyWeather(
            requested_date=requested_date,
            source_date=requested_date,
            source="forecast",
            minimum_c=min(_decimal(sample[1]["main"]["temp_min"]) for sample in samples),
            maximum_c=max(_decimal(sample[1]["main"]["temp_max"]) for sample in samples),
            representative_c=_decimal(representative["main"]["temp"]),
            condition=dominant,
            precipitation_probability_percent=max(
                round(float(sample[1].get("pop", 0)) * 100) for sample in samples
            ),
            humidity_percent=humidity,
            maximum_wind_kph=max(
                _decimal(Decimal(str(sample[1]["wind"]["speed"])) * Decimal("3.6"))
                for sample in samples
            ),
        )
    return rows


def _shift_year(value: date, years: int) -> date:
    target_year = value.year - years
    target_day = value.day
    if value.month == 2 and value.day == 29 and not calendar.isleap(target_year):
        target_day = 28
    return date(target_year, value.month, target_day)


def _historical_date_map(requested_dates: list[date], archive_cutoff: date) -> dict[date, date]:
    if requested_dates and max(requested_dates) <= archive_cutoff:
        return {value: value for value in requested_dates}

    years = 1
    while True:
        mapped = {value: _shift_year(value, years) for value in requested_dates}
        if mapped and max(mapped.values()) <= archive_cutoff:
            return mapped
        years += 1


def _consecutive_groups(values: list[date]) -> list[tuple[date, date]]:
    if not values:
        return []
    groups: list[tuple[date, date]] = []
    start = previous = values[0]
    for current in values[1:]:
        if current != previous + timedelta(days=1):
            groups.append((start, previous))
            start = current
        previous = current
    groups.append((start, previous))
    return groups


def _parse_historical(payload: dict) -> dict[date, dict]:
    daily = payload["daily"]
    dates = daily["time"]
    fields = {
        "maximum": daily["temperature_2m_max"],
        "minimum": daily["temperature_2m_min"],
        "mean": daily["temperature_2m_mean"],
        "precipitation": daily["precipitation_sum"],
        "weather_code": daily["weather_code"],
        "wind": daily["wind_speed_10m_max"],
    }
    if any(len(values) != len(dates) for values in fields.values()):
        raise WeatherProviderError("weather provider unavailable")
    return {
        date.fromisoformat(source_date): {key: values[index] for key, values in fields.items()}
        for index, source_date in enumerate(dates)
    }


async def _historical_rows(
    *,
    client: httpx.AsyncClient,
    latitude: float,
    longitude: float,
    requested_dates: list[date],
    archive_cutoff: date,
) -> dict[date, DailyWeather]:
    mapped_dates = _historical_date_map(requested_dates, archive_cutoff)
    historical_by_source: dict[date, dict] = {}
    unique_sources = sorted(set(mapped_dates.values()))
    for start, end in _consecutive_groups(unique_sources):
        response = await client.get(
            OPEN_METEO_ARCHIVE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": OPEN_METEO_DAILY_FIELDS,
                "timezone": "auto",
            },
            timeout=12.0,
        )
        response.raise_for_status()
        historical_by_source.update(_parse_historical(response.json()))

    rows: dict[date, DailyWeather] = {}
    for requested_date, source_date in mapped_dates.items():
        values = historical_by_source[source_date]
        rows[requested_date] = DailyWeather(
            requested_date=requested_date,
            source_date=source_date,
            source="historical",
            minimum_c=_decimal(values["minimum"]),
            maximum_c=_decimal(values["maximum"]),
            representative_c=_decimal(values["mean"]),
            condition=_wmo_condition(int(values["weather_code"])),
            precipitation_probability_percent=None,
            precipitation_mm=_decimal(values["precipitation"]),
            humidity_percent=None,
            maximum_wind_kph=_decimal(values["wind"]),
        )
    return rows


async def get_weather_report(
    destination: str,
    start_date: date,
    end_date: date,
    *,
    client: httpx.AsyncClient | None = None,
    today: date | None = None,
) -> WeatherReport:
    settings = get_settings()
    api_key = settings.openweather_api_key
    if not api_key:
        raise WeatherProviderError("weather provider unavailable")

    owns_client = client is None
    active_client = client or httpx.AsyncClient()
    try:
        geocoding_response = await active_client.get(
            OPENWEATHER_GEOCODING_URL,
            params={"q": destination, "limit": 1, "appid": api_key},
            timeout=8.0,
        )
        geocoding_response.raise_for_status()
        geocoding = geocoding_response.json()
        if not isinstance(geocoding, list) or not geocoding:
            raise WeatherProviderError("weather provider unavailable")
        resolved = geocoding[0]
        latitude = float(resolved["lat"])
        longitude = float(resolved["lon"])

        current_response, forecast_response = await asyncio.gather(
            active_client.get(
                OPENWEATHER_CURRENT_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "appid": api_key,
                    "units": "metric",
                },
                timeout=8.0,
            ),
            active_client.get(
                OPENWEATHER_FORECAST_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "appid": api_key,
                    "units": "metric",
                },
                timeout=8.0,
            ),
        )
        current_response.raise_for_status()
        forecast_response.raise_for_status()
        current_payload = current_response.json()
        forecast_payload = forecast_response.json()
        offset_seconds = int(current_payload["timezone"])
        current = _parse_current(current_payload, offset_seconds)

        requested_dates = _date_range(start_date, end_date)
        daily_by_date = _aggregate_forecast(
            forecast_payload,
            set(requested_dates),
            offset_seconds,
        )
        uncovered = [value for value in requested_dates if value not in daily_by_date]
        if uncovered:
            daily_by_date.update(
                await _historical_rows(
                    client=active_client,
                    latitude=latitude,
                    longitude=longitude,
                    requested_dates=uncovered,
                    archive_cutoff=(today or date.today()) - timedelta(days=5),
                )
            )

        location_name = str(current_payload.get("name") or resolved["name"])
        country_code = str(current_payload.get("sys", {}).get("country") or resolved["country"])
        return WeatherReport(
            location=ResolvedLocation(
                name=location_name,
                country_code=country_code,
                latitude=latitude,
                longitude=longitude,
                timezone_offset_seconds=offset_seconds,
            ),
            current=current,
            daily=[daily_by_date[value] for value in requested_dates],
            source="openweather+open-meteo" if uncovered else "openweather",
            summary=(
                f"Current conditions in {location_name}: {current.description}, "
                f"{current.temperature_c}°C, {current.humidity_percent}% humidity, "
                f"wind {current.wind_speed_kph} km/h."
            ),
        )
    except WeatherProviderError:
        raise
    except Exception:
        raise WeatherProviderError("weather provider unavailable") from None
    finally:
        if owns_client:
            await active_client.aclose()
