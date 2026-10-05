from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LocationType = Literal["city", "town", "region", "state", "island", "country"]
LocationKind = Literal["departure", "destination"]


class LocationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=300)
    country_code: str = Field(min_length=2, max_length=2)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_type: LocationType

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("location label must not be empty")
        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        return value.upper()


class LocationSuggestion(LocationSelection):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("location name must not be empty")
        return value
