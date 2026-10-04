import asyncio
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import TripStatus
from app.core.exceptions import ValidationError
from app.models import Place, Trip
from app.providers.catalog import get_candidate_places
from app.providers.weather import get_weather
from app.schemas.common import money
from app.schemas.place import AnalysisResponse, BudgetEstimate, PlaceRead

STYLE_MULTIPLIER = {
    "BUDGET": Decimal("0.72"),
    "COMFORTABLE": Decimal("1.00"),
    "PREMIUM": Decimal("1.65"),
}


def estimate_budget(trip: Trip) -> BudgetEstimate:
    daily_per_person = Decimal("6200") * STYLE_MULTIPLIER[trip.travel_style]
    travelers = max(1, len(trip.travelers))
    typical = money(daily_per_person * trip.number_of_days * travelers)
    return BudgetEstimate(
        minimum=money(typical * Decimal("0.72")),
        typical=typical,
        maximum=money(typical * Decimal("1.38")),
        currency=trip.base_currency,
    )


def _bounded(value: Decimal) -> Decimal:
    return min(Decimal("10"), max(Decimal("0"), value)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def _place_from_catalog(trip: Trip, item: dict, weather_score: Decimal) -> Place:
    days = Decimal(str(item["days"]))
    factor = Decimal(str(item["factor"])) * STYLE_MULTIPLIER[trip.travel_style]
    daily = Decimal("5200") * factor
    stay = money(daily * days * Decimal("0.42"))
    food = money(daily * days * Decimal("0.20"))
    transport = money(daily * days * Decimal("0.14"))
    tickets = money(daily * days * Decimal("0.08"))
    activity = money(daily * days * Decimal("0.16"))
    duration_fit = _bounded(Decimal("10") - abs(days - Decimal(trip.number_of_days) / 3))
    total = stay + food + transport + tickets + activity
    per_place_budget = (trip.budget or total * 5) / Decimal("5")
    budget_fit = _bounded(Decimal("10") - max(Decimal("0"), total - per_place_budget) / 2000)
    efficiency = _bounded(Decimal("9") - days / 3)
    interest = Decimal("8.5")
    overall = _bounded(
        weather_score * Decimal("0.25")
        + interest * Decimal("0.25")
        + duration_fit * Decimal("0.20")
        + budget_fit * Decimal("0.20")
        + efficiency * Decimal("0.10")
    )
    return Place(
        trip_id=trip.id,
        name=item["name"],
        description=item["description"],
        latitude=item["latitude"],
        longitude=item["longitude"],
        recommended_days=days,
        estimated_food=food,
        estimated_transport=transport,
        estimated_tickets=tickets,
        estimated_activity=activity,
        estimated_stay=stay,
        weather_score=weather_score,
        overall_score=overall,
        best_for=item["best_for"],
        selected=False,
    )


async def analyze_trip(db: Session, trip: Trip) -> AnalysisResponse:
    weather, catalog = await asyncio.gather(
        get_weather(trip.destination, trip.start_date),
        get_candidate_places(trip.destination),
    )
    budget = estimate_budget(trip)
    db.execute(delete(Place).where(Place.trip_id == trip.id))
    places = [_place_from_catalog(trip, item, weather.score) for item in catalog]
    db.add_all(places)
    trip.weather_score = weather.score
    trip.weather_rating = weather.rating
    trip.weather_summary = weather.summary
    trip.estimated_cost_min = budget.minimum
    trip.estimated_cost = budget.typical
    trip.estimated_cost_max = budget.maximum
    trip.status = TripStatus.READY.value
    db.commit()
    for place in places:
        db.refresh(place)
    return AnalysisResponse(
        weather=weather,
        estimated_budget=budget,
        places=[PlaceRead.model_validate(place) for place in places],
        status=trip.status,
    )


def list_places(db: Session, trip: Trip) -> list[Place]:
    return list(
        db.scalars(
            select(Place).where(Place.trip_id == trip.id).order_by(Place.overall_score.desc())
        )
    )


def select_places(db: Session, trip: Trip, place_ids: list[str]) -> list[Place]:
    unique_ids = set(place_ids)
    places = list(db.scalars(select(Place).where(Place.id.in_(unique_ids))))
    if len(places) != len(unique_ids) or any(place.trip_id != trip.id for place in places):
        raise ValidationError("One or more places do not belong to this trip")
    all_trip_places = list(db.scalars(select(Place).where(Place.trip_id == trip.id)))
    for place in all_trip_places:
        place.selected = place.id in unique_ids
    db.commit()
    return [place for place in all_trip_places if place.selected]
