from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import TravelStyle, TripStatus
from app.schemas.location import LocationSelection


class TripCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    departure_city: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    departure_location: LocationSelection | None = None
    destination_location: LocationSelection | None = None
    start_date: date
    number_of_days: int = Field(gt=0, le=60)
    budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    travel_style: TravelStyle = TravelStyle.COMFORTABLE

    @field_validator("name", "departure_city", "destination")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class TravelerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Traveler name cannot be empty")
        return value


class TravelerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str | None
    created_at: datetime


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    departure_city: str | None
    departure_location: LocationSelection | None
    destination: str
    destination_location: LocationSelection | None
    start_date: date
    end_date: date
    number_of_days: int
    base_currency: str
    budget: Decimal | None
    travel_style: TravelStyle
    status: TripStatus
    is_archived: bool
    archived_at: datetime | None
    weather_score: Decimal | None
    weather_rating: str | None
    weather_summary: str | None
    estimated_cost_min: Decimal | None
    estimated_cost: Decimal | None
    estimated_cost_max: Decimal | None
    travelers: list[TravelerRead] = []
    created_at: datetime
    updated_at: datetime


class TripCreated(BaseModel):
    trip_id: str
    status: TripStatus
