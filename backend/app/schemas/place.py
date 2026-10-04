from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WeatherAnalysis(BaseModel):
    score: Decimal = Field(ge=0, le=10)
    rating: str
    summary: str
    temperature_c: Decimal
    rain_probability: int = Field(ge=0, le=100)
    humidity: int = Field(ge=0, le=100)
    wind_kph: Decimal = Field(ge=0)


class BudgetEstimate(BaseModel):
    minimum: Decimal
    typical: Decimal
    maximum: Decimal
    currency: str


class PlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    latitude: float
    longitude: float
    recommended_days: Decimal
    estimated_food: Decimal
    estimated_transport: Decimal
    estimated_tickets: Decimal
    estimated_activity: Decimal
    estimated_stay: Decimal
    estimated_cost: Decimal
    weather_score: Decimal
    overall_score: Decimal
    best_for: list[str]
    selected: bool


class PlaceSelection(BaseModel):
    place_ids: list[str] = Field(min_length=1)


class AnalysisResponse(BaseModel):
    weather: WeatherAnalysis
    estimated_budget: BudgetEstimate
    places: list[PlaceRead]
    status: str = "READY"
