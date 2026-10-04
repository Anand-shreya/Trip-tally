from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActivityPlan(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str
    activity_type: str = Field(max_length=50)
    start_time: time
    end_time: time
    location_name: str
    latitude: float | None = None
    longitude: float | None = None
    estimated_cost: Decimal = Field(default=0, ge=0)

    @model_validator(mode="after")
    def times_are_ordered(self):
        if self.start_time >= self.end_time:
            raise ValueError("Activity start time must be before end time")
        return self


class ItineraryDayPlan(BaseModel):
    day: int = Field(gt=0)
    date: date
    title: str = Field(min_length=1, max_length=200)
    summary: str
    activities: list[ActivityPlan]


class ItineraryPlan(BaseModel):
    days: list[ItineraryDayPlan]


class ActivityRead(ActivityPlan):
    model_config = ConfigDict(from_attributes=True)

    id: str


class ItineraryDayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    day_number: int
    date: date
    title: str
    summary: str
    activities: list[ActivityRead]


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    type: str
    status: str
    attempt: int
    max_attempts: int
    result: dict | None
    error: str | None
