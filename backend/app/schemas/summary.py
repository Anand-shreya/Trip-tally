from decimal import Decimal

from pydantic import BaseModel

from app.schemas.expense import Settlement, TravelerBalance


class TripSummary(BaseModel):
    trip_id: str
    trip_name: str
    destination: str
    days: int
    currency: str
    budget: Decimal | None
    total_spent: Decimal
    remaining: Decimal | None
    average_per_day: Decimal
    categories: dict[str, Decimal]
    most_expensive_category: str | None
    most_expensive_expense: str | None
    traveler_balances: list[TravelerBalance]
    settlements: list[Settlement]
    ai_summary: str

