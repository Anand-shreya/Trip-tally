from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from app.providers import weather as weather_module


def unix(iso_value: str) -> int:
    return int(datetime.fromisoformat(iso_value).replace(tzinfo=UTC).timestamp())


def current_payload() -> dict:
    return {
        "coord": {"lon": 77.2167, "lat": 28.6667},
        "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
        "main": {
            "temp": 28.4,
            "feels_like": 29.0,
            "temp_min": 27.0,
            "temp_max": 29.0,
            "pressure": 1012,
            "humidity": 65,
        },
        "visibility": 10000,
        "wind": {"speed": 5.0, "deg": 280},
        "clouds": {"all": 0},
        "rain": {"1h": 0.4},
        "dt": unix("2026-10-05T12:00:00"),
        "sys": {
            "country": "IN",
            "sunrise": unix("2026-10-05T00:40:00"),
            "sunset": unix("2026-10-05T12:35:00"),
        },
        "timezone": 19800,
        "name": "Delhi",
    }


def forecast_sample(
    iso_value: str,
    *,
    temperature: float,
    condition: str = "Clouds",
    description: str = "scattered clouds",
    probability: float = 0.2,
    humidity: int = 60,
    wind_mps: float = 3.0,
) -> dict:
    return {
        "dt": unix(iso_value),
        "main": {
            "temp": temperature,
            "temp_min": temperature - 1,
            "temp_max": temperature + 1,
            "humidity": humidity,
        },
        "weather": [{"main": condition, "description": description}],
        "clouds": {"all": 30},
        "wind": {"speed": wind_mps, "deg": 120},
        "pop": probability,
    }


def historical_payload(start_date: date, end_date: date) -> dict:
    dates: list[str] = []
    cursor = start_date
    while cursor <= end_date:
        dates.append(cursor.isoformat())
        cursor += timedelta(days=1)
    count = len(dates)
    return {
        "timezone": "Asia/Kolkata",
        "daily": {
            "time": dates,
            "temperature_2m_max": [30.0] * count,
            "temperature_2m_min": [20.0] * count,
            "temperature_2m_mean": [25.0] * count,
            "precipitation_sum": [1.5] * count,
            "weather_code": [61] * count,
            "wind_speed_10m_max": [12.0] * count,
        },
    }


def complete_handler(forecast_items: list[dict], observed_archive_calls: list[tuple[date, date]]):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/geo/1.0/direct":
            assert request.url.params["q"] == "Delhi"
            assert request.url.params["limit"] == "1"
            assert request.url.params["appid"] == "test-weather-key"
            return httpx.Response(
                200,
                json=[{"name": "Delhi", "lat": 28.6667, "lon": 77.2167, "country": "IN"}],
            )
        if request.url.path == "/data/2.5/weather":
            assert request.url.params["lat"] == "28.6667"
            assert request.url.params["lon"] == "77.2167"
            assert request.url.params["units"] == "metric"
            return httpx.Response(200, json=current_payload())
        if request.url.path == "/data/2.5/forecast":
            return httpx.Response(
                200,
                json={"city": {"timezone": 19800}, "list": forecast_items},
            )
        if request.url.host == "archive-api.open-meteo.com":
            start = date.fromisoformat(request.url.params["start_date"])
            end = date.fromisoformat(request.url.params["end_date"])
            observed_archive_calls.append((start, end))
            assert request.url.params["timezone"] == "auto"
            assert request.url.params["daily"] == (
                "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                "precipitation_sum,weather_code,wind_speed_10m_max"
            )
            return httpx.Response(200, json=historical_payload(start, end))
        raise AssertionError(f"Unexpected provider path: {request.url.path}")

    return handler


def configure(monkeypatch, api_key: str | None = "test-weather-key") -> None:
    monkeypatch.setattr(
        weather_module,
        "get_settings",
        lambda: SimpleNamespace(openweather_api_key=api_key),
    )


@pytest.mark.asyncio
async def test_weather_report_combines_complete_current_forecast_and_historical_data(monkeypatch):
    configure(monkeypatch)
    archive_calls: list[tuple[date, date]] = []
    forecast = [
        forecast_sample("2026-10-06T00:00:00", temperature=22.0, probability=0.1),
        forecast_sample(
            "2026-10-06T06:00:00",
            temperature=27.0,
            condition="Clear",
            description="clear sky",
            probability=0.4,
            humidity=70,
            wind_mps=4.0,
        ),
        forecast_sample("2026-10-07T00:00:00", temperature=23.0, probability=0.3),
        forecast_sample("2026-10-07T06:00:00", temperature=29.0, probability=0.5),
    ]
    transport = httpx.MockTransport(complete_handler(forecast, archive_calls))

    async with httpx.AsyncClient(transport=transport) as client:
        report = await weather_module.get_weather_report(
            "Delhi",
            date(2026, 10, 6),
            date(2026, 10, 8),
            client=client,
            today=date(2026, 10, 5),
        )

    assert report.location.name == "Delhi"
    assert report.location.country_code == "IN"
    assert report.location.timezone_offset_seconds == 19800
    assert report.current.condition == "Clear"
    assert report.current.description == "clear sky"
    assert report.current.temperature_c == Decimal("28.4")
    assert report.current.feels_like_c == Decimal("29.0")
    assert report.current.minimum_c == Decimal("27.0")
    assert report.current.maximum_c == Decimal("29.0")
    assert report.current.humidity_percent == 65
    assert report.current.pressure_hpa == 1012
    assert report.current.visibility_m == 10000
    assert report.current.cloud_percent == 0
    assert report.current.wind_speed_kph == Decimal("18.0")
    assert report.current.wind_direction_degrees == 280
    assert report.current.rain_mm_1h == Decimal("0.4")
    assert report.current.snow_mm_1h is None
    assert report.summary == (
        "Current conditions in Delhi: clear sky, 28.4°C, 65% humidity, wind 18.0 km/h."
    )
    assert [row.requested_date for row in report.daily] == [
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
    ]
    assert report.daily[0].source == "forecast"
    assert report.daily[0].minimum_c == Decimal("21.0")
    assert report.daily[0].maximum_c == Decimal("28.0")
    assert report.daily[0].representative_c == Decimal("27.0")
    assert report.daily[0].precipitation_probability_percent == 40
    assert report.daily[0].humidity_percent == 65
    assert report.daily[0].maximum_wind_kph == Decimal("14.4")
    assert report.daily[-1].source == "historical"
    assert report.daily[-1].source_date == date(2025, 10, 8)
    assert report.daily[-1].condition == "Rain"
    assert report.source == "openweather+open-meteo"
    assert archive_calls == [(date(2025, 10, 8), date(2025, 10, 8))]


@pytest.mark.asyncio
async def test_forecast_samples_are_grouped_by_resolved_local_date(monkeypatch):
    configure(monkeypatch)
    archive_calls: list[tuple[date, date]] = []
    forecast = [
        forecast_sample("2026-10-05T20:00:00", temperature=21.0),
        forecast_sample("2026-10-06T06:00:00", temperature=27.0),
    ]
    transport = httpx.MockTransport(complete_handler(forecast, archive_calls))

    async with httpx.AsyncClient(transport=transport) as client:
        report = await weather_module.get_weather_report(
            "Delhi",
            date(2026, 10, 6),
            date(2026, 10, 6),
            client=client,
            today=date(2026, 10, 5),
        )

    assert len(report.daily) == 1
    assert report.daily[0].requested_date == date(2026, 10, 6)
    assert report.daily[0].source == "forecast"
    assert archive_calls == []


@pytest.mark.asyncio
async def test_past_trip_uses_actual_archived_dates(monkeypatch):
    configure(monkeypatch)
    archive_calls: list[tuple[date, date]] = []
    transport = httpx.MockTransport(complete_handler([], archive_calls))

    async with httpx.AsyncClient(transport=transport) as client:
        report = await weather_module.get_weather_report(
            "Delhi",
            date(2026, 1, 2),
            date(2026, 1, 3),
            client=client,
            today=date(2026, 10, 5),
        )

    assert archive_calls == [(date(2026, 1, 2), date(2026, 1, 3))]
    assert [row.source_date for row in report.daily] == [date(2026, 1, 2), date(2026, 1, 3)]


@pytest.mark.asyncio
async def test_future_cross_year_trip_uses_latest_complete_historical_span(monkeypatch):
    configure(monkeypatch)
    archive_calls: list[tuple[date, date]] = []
    transport = httpx.MockTransport(complete_handler([], archive_calls))

    async with httpx.AsyncClient(transport=transport) as client:
        report = await weather_module.get_weather_report(
            "Delhi",
            date(2027, 12, 30),
            date(2028, 1, 2),
            client=client,
            today=date(2026, 10, 5),
        )

    assert archive_calls == [(date(2025, 12, 30), date(2026, 1, 2))]
    assert [row.source_date for row in report.daily] == [
        date(2025, 12, 30),
        date(2025, 12, 31),
        date(2026, 1, 1),
        date(2026, 1, 2),
    ]


@pytest.mark.asyncio
async def test_future_leap_day_maps_to_february_28_in_non_leap_source_year(monkeypatch):
    configure(monkeypatch)
    archive_calls: list[tuple[date, date]] = []
    transport = httpx.MockTransport(complete_handler([], archive_calls))

    async with httpx.AsyncClient(transport=transport) as client:
        report = await weather_module.get_weather_report(
            "Delhi",
            date(2028, 2, 29),
            date(2028, 2, 29),
            client=client,
            today=date(2026, 10, 5),
        )

    assert archive_calls == [(date(2026, 2, 28), date(2026, 2, 28))]
    assert report.daily[0].requested_date == date(2028, 2, 29)
    assert report.daily[0].source_date == date(2026, 2, 28)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["empty_geocode", "malformed_current", "upstream_503"])
async def test_weather_failures_raise_one_safe_error(monkeypatch, failure):
    configure(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "upstream_503":
            return httpx.Response(503, json={"message": "secret upstream detail"})
        if request.url.path == "/geo/1.0/direct":
            if failure == "empty_geocode":
                return httpx.Response(200, json=[])
            return httpx.Response(
                200,
                json=[{"name": "Delhi", "lat": 28.6667, "lon": 77.2167, "country": "IN"}],
            )
        if request.url.path == "/data/2.5/weather":
            return httpx.Response(200, json={"main": {}})
        return httpx.Response(200, json={"city": {"timezone": 19800}, "list": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Exception) as captured:
            await weather_module.get_weather_report(
                "Delhi",
                date(2026, 10, 6),
                date(2026, 10, 6),
                client=client,
                today=date(2026, 10, 5),
            )

    assert captured.type is weather_module.WeatherProviderError
    assert str(captured.value) == "weather provider unavailable"
    assert "test-weather-key" not in str(captured.value)
    assert "secret upstream detail" not in str(captured.value)


@pytest.mark.asyncio
async def test_missing_openweather_key_never_falls_back(monkeypatch):
    configure(monkeypatch, api_key=None)

    with pytest.raises(Exception) as captured:
        await weather_module.get_weather_report(
            "Delhi",
            date(2026, 10, 6),
            date(2026, 10, 6),
            today=date(2026, 10, 5),
        )

    assert captured.type is weather_module.WeatherProviderError
    assert str(captured.value) == "weather provider unavailable"
