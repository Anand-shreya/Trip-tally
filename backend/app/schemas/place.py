from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    latitude: float
    longitude: float
    recommended_days: Decimal
    relevance_score: Decimal
    best_for: list[str]
    selected: bool


class PlaceSelection(BaseModel):
    place_ids: list[str] = Field(min_length=1)
