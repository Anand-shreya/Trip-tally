import json
from datetime import time, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.models import Place, Trip
from app.schemas.itinerary import ActivityPlan, ItineraryDayPlan, ItineraryPlan


class SummaryNarrative(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)


def _provider(client: Any | None, model: str | None) -> tuple[Any | None, str]:
    settings = get_settings()
    if client is not None:
        return client, model or settings.openai_model
    if not settings.openai_enabled or not settings.openai_api_key:
        return None, model or settings.openai_model
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key), model or settings.openai_model


def generate_local_itinerary(trip: Trip, places: list[Place]) -> ItineraryPlan:
    """Build the complete deterministic itinerary used without an API key."""
    days: list[ItineraryDayPlan] = []
    for index in range(trip.number_of_days):
        place = places[index % len(places)]
        current_date = trip.start_date + timedelta(days=index)
        morning = ActivityPlan(
            title=f"Explore {place.name}",
            description=(
                f"Start with the essential sights and stories of {place.name} at an unhurried pace."
            ),
            activity_type="SIGHTSEEING",
            start_time=time(9, 0),
            end_time=time(12, 0),
            location_name=place.name,
            latitude=place.latitude,
            longitude=place.longitude,
            estimated_cost=(place.estimated_tickets + place.estimated_activity)
            / max(1, trip.number_of_days),
        )
        evening = ActivityPlan(
            title="Local table",
            description=(
                "Choose a well-reviewed local restaurant and leave room for a slow evening walk."
            ),
            activity_type="FOOD",
            start_time=time(18, 30),
            end_time=time(20, 30),
            location_name=place.name,
            latitude=place.latitude,
            longitude=place.longitude,
            estimated_cost=place.estimated_food / max(1, trip.number_of_days),
        )
        days.append(
            ItineraryDayPlan(
                day=index + 1,
                date=current_date,
                title=f"{place.name} — day {index + 1}",
                summary=f"A balanced day of discovery and downtime in {place.name}.",
                activities=[morning, evening],
            )
        )
    return ItineraryPlan(days=days)


def generate_itinerary(
    trip: Trip,
    places: list[Place],
    *,
    client: Any | None = None,
    model: str | None = None,
) -> ItineraryPlan:
    """Generate a schema-validated itinerary through Responses or the local provider."""
    provider, selected_model = _provider(client, model)
    if provider is None:
        return generate_local_itinerary(trip, places)

    facts = {
        "trip": {
            "name": trip.name,
            "destination": trip.destination,
            "start_date": trip.start_date.isoformat(),
            "number_of_days": trip.number_of_days,
            "currency": trip.base_currency,
            "budget": trip.budget,
            "weather_summary": trip.weather_summary,
        },
        "selected_places": [
            {
                "name": place.name,
                "description": place.description,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "recommended_days": place.recommended_days,
                "estimated_cost": place.estimated_cost,
                "best_for": place.best_for,
            }
            for place in places
        ],
    }
    response = provider.responses.parse(
        model=selected_model,
        input=[
            {
                "role": "system",
                "content": (
                    "Create a practical day-by-day travel itinerary from verified facts. "
                    "Return exactly the requested days and dates, keep start times before end "
                    "times, and set activity estimated_cost to 0 because the backend owns money."
                ),
            },
            {"role": "user", "content": json.dumps(facts, default=str)},
        ],
        text_format=ItineraryPlan,
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no structured itinerary")
    return response.output_parsed


def _generate_local_summary_text(
    *, budget: Decimal | None, total_spent: Decimal, top_category: str | None, currency: str
) -> str:
    category_text = (
        f" {top_category.title()} was the largest spending category." if top_category else ""
    )
    if budget is None:
        return f"The trip recorded {total_spent:.2f} {currency} in shared spending.{category_text}"
    difference = budget - total_spent
    if difference >= 0:
        return (
            f"You stayed within the {budget:.2f} {currency} budget, with {difference:.2f} "
            f"{currency} remaining.{category_text}"
        )
    return (
        f"The trip finished {abs(difference):.2f} {currency} over the {budget:.2f} "
        f"{currency} budget.{category_text}"
    )


def generate_summary_text(
    *,
    budget: Decimal | None,
    total_spent: Decimal,
    top_category: str | None,
    currency: str,
    client: Any | None = None,
    model: str | None = None,
) -> str:
    """Turn backend-owned financial facts into prose without delegating calculations."""
    provider, selected_model = _provider(client, model)
    if provider is None:
        return _generate_local_summary_text(
            budget=budget,
            total_spent=total_spent,
            top_category=top_category,
            currency=currency,
        )
    difference = budget - total_spent if budget is not None else None
    facts = {
        "budget": budget,
        "total_spent": total_spent,
        "remaining": difference if budget is not None else None,
        "top_category": top_category,
        "currency": currency,
    }
    try:
        response = provider.responses.parse(
            model=selected_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Write a concise, friendly trip-spending summary using only the verified "
                        "facts supplied. Do not calculate or change any number."
                    ),
                },
                {"role": "user", "content": json.dumps(facts, default=str)},
            ],
            text_format=SummaryNarrative,
        )
    except Exception:
        return _generate_local_summary_text(
            budget=budget,
            total_spent=total_spent,
            top_category=top_category,
            currency=currency,
        )
    if response.output_parsed is None:
        return _generate_local_summary_text(
            budget=budget,
            total_spent=total_spent,
            top_category=top_category,
            currency=currency,
        )
    return response.output_parsed.summary
