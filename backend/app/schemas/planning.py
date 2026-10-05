from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import TravelStyle
from app.schemas.place import PlaceRead


class AnalyzeTripRequest(BaseModel):
    departure_city: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("departure_city")
    @classmethod
    def strip_departure_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("departure city must not be empty")
        return value


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


class EstimateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum: Decimal = Field(ge=0)
    typical: Decimal = Field(ge=0)
    maximum: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "EstimateRange":
        if not self.minimum <= self.typical <= self.maximum:
            raise ValueError("estimate range must be ordered")
        return self


class BudgetCategories(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flights: EstimateRange
    accommodation: EstimateRange
    food: EstimateRange
    local_transport: EstimateRange
    tickets: EstimateRange
    activities: EstimateRange


class BudgetFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departure_city: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    start_date: date
    number_of_days: int = Field(ge=1, le=60)
    traveler_count: int = Field(ge=1)
    travel_style: TravelStyle
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_validator("departure_city", "destination")
    @classmethod
    def strip_city(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("city must not be empty")
        return value


class GeminiBudgetResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(pattern=r"^[A-Z]{3}$")
    categories: BudgetCategories


class BudgetReport(BaseModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    traveler_count: int = Field(ge=1)
    number_of_days: int = Field(ge=1)
    categories: BudgetCategories
    total: EstimateRange


Tag = Annotated[str, Field(min_length=1, max_length=40)]


class PlaceSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=240)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    recommended_days: Decimal = Field(ge=Decimal("0.5"))
    best_for: list[Tag] = Field(max_length=4)
    relevance_score: Decimal = Field(ge=0, le=10)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be empty")
        return value

    @field_validator("best_for", mode="before")
    @classmethod
    def strip_tags(cls, value: object) -> object:
        if isinstance(value, list):
            return [item.strip() if isinstance(item, str) else item for item in value]
        return value


class PlaceFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1, max_length=200)
    number_of_days: int = Field(ge=1, le=60)
    travel_style: TravelStyle
    maximum_results: Literal[20] = 20

    @field_validator("destination")
    @classmethod
    def strip_destination(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("destination must not be empty")
        return value


class GeminiPlacesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    places: list[PlaceSuggestion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_place_count(self) -> "GeminiPlacesResult":
        if len(self.places) > 20:
            raise ValueError("at most 20 places are allowed")
        return self


class AnalysisResponse(BaseModel):
    weather: WeatherReport
    budget: BudgetReport
    places: list[PlaceRead]
    weather_source: str
    budget_model: str
    analyzed_at: datetime
    status: str

    @field_validator("analyzed_at")
    @classmethod
    def normalize_analyzed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
