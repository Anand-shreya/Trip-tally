from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ResolvedLocation(BaseModel):
    name: str
    country_code: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone_offset_seconds: int


class CurrentWeather(BaseModel):
    observed_at: datetime
    condition: str
    description: str
    temperature_c: Decimal
    feels_like_c: Decimal
    minimum_c: Decimal
    maximum_c: Decimal
    humidity_percent: int = Field(ge=0, le=100)
    pressure_hpa: int = Field(gt=0)
    visibility_m: int = Field(ge=0)
    cloud_percent: int = Field(ge=0, le=100)
    wind_speed_kph: Decimal = Field(ge=0)
    wind_direction_degrees: int = Field(ge=0, le=360)
    rain_mm_1h: Decimal | None = Field(default=None, ge=0)
    snow_mm_1h: Decimal | None = Field(default=None, ge=0)
    sunrise_at: datetime
    sunset_at: datetime


class DailyWeather(BaseModel):
    requested_date: date
    source_date: date
    source: Literal["forecast", "historical"]
    minimum_c: Decimal
    maximum_c: Decimal
    representative_c: Decimal
    condition: str
    precipitation_probability_percent: int | None = Field(default=None, ge=0, le=100)
    precipitation_mm: Decimal | None = Field(default=None, ge=0)
    humidity_percent: int | None = Field(default=None, ge=0, le=100)
    maximum_wind_kph: Decimal = Field(ge=0)


class WeatherReport(BaseModel):
    location: ResolvedLocation
    current: CurrentWeather
    daily: list[DailyWeather]
    source: Literal["openweather", "openweather+open-meteo"]
    summary: str
