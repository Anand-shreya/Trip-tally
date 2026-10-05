import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import TripStatus
from app.core.exceptions import NotFoundError, ProviderError, ValidationError
from app.models import Place, Trip, TripPlanningProfile
from app.models.base import utc_now
from app.providers.gemini_planning import (
    InvalidPlanningResponse,
    build_gemini_planning_provider,
)
from app.providers.weather import get_weather_report
from app.schemas.place import PlaceRead
from app.schemas.planning import (
    AnalysisResponse,
    AnalyzeTripRequest,
    BudgetFacts,
    BudgetReport,
    PlaceFacts,
    PlaceSuggestion,
    WeatherReport,
)

WeatherFetcher = Callable[
    [str, date, date, float | None, float | None, str | None],
    Awaitable[WeatherReport],
]


class PlanningAIProvider(Protocol):
    model: str

    async def estimate_budget(self, facts: BudgetFacts) -> BudgetReport:
        raise NotImplementedError

    async def discover_places(self, facts: PlaceFacts) -> list[PlaceSuggestion]:
        raise NotImplementedError


def _provider_error(result: object, stage: str) -> ProviderError | None:
    if not isinstance(result, BaseException):
        return None
    if isinstance(result, (InvalidPlanningResponse, PydanticValidationError)):
        return ProviderError("invalid_provider_response")
    if stage == "weather":
        return ProviderError("weather_unavailable")
    if stage == "budget":
        return ProviderError("budget_unavailable")
    return ProviderError("places_unavailable")


def _persisted_response(db: Session, trip: Trip) -> AnalysisResponse:
    profile = trip.planning_profile
    if (
        profile is None
        or profile.weather_report is None
        or profile.budget_report is None
        or profile.weather_source is None
        or profile.budget_model is None
        or profile.analyzed_at is None
    ):
        raise NotFoundError("Analysis not found")
    return AnalysisResponse(
        weather=WeatherReport.model_validate(profile.weather_report),
        budget=BudgetReport.model_validate(profile.budget_report),
        places=[PlaceRead.model_validate(place) for place in list_places(db, trip)],
        weather_source=profile.weather_source,
        budget_model=profile.budget_model,
        analyzed_at=profile.analyzed_at,
        status=trip.status,
    )


async def analyze_trip(
    db: Session,
    trip: Trip,
    payload: AnalyzeTripRequest,
    *,
    weather_fetcher: WeatherFetcher | None = None,
    planning_provider: PlanningAIProvider | None = None,
) -> AnalysisResponse:
    departure_city = payload.departure_city or trip.departure_city
    if departure_city is None:
        raise ValidationError("Departure city is required before analysis")

    active_weather_fetcher = weather_fetcher or get_weather_report
    owns_planning_provider = planning_provider is None
    if planning_provider is None:
        try:
            active_planning_provider = build_gemini_planning_provider()
        except InvalidPlanningResponse:
            raise ProviderError("invalid_provider_response") from None
        except Exception:
            raise ProviderError("budget_unavailable") from None
    else:
        active_planning_provider = planning_provider

    traveler_count = max(1, len(trip.travelers))
    budget_facts = BudgetFacts(
        departure_city=departure_city,
        destination=trip.destination,
        start_date=trip.start_date,
        number_of_days=trip.number_of_days,
        traveler_count=traveler_count,
        travel_style=trip.travel_style,
        currency=trip.base_currency,
    )
    place_facts = PlaceFacts(
        destination=trip.destination,
        number_of_days=trip.number_of_days,
        travel_style=trip.travel_style,
    )
    destination_location = trip.destination_location

    try:
        weather_result, budget_result, places_result = await asyncio.gather(
            active_weather_fetcher(
                trip.destination,
                trip.start_date,
                trip.end_date,
                destination_location.latitude if destination_location else None,
                destination_location.longitude if destination_location else None,
                destination_location.country_code if destination_location else None,
            ),
            active_planning_provider.estimate_budget(budget_facts),
            active_planning_provider.discover_places(place_facts),
            return_exceptions=True,
        )
    finally:
        if owns_planning_provider:
            close = getattr(active_planning_provider, "close", None)
            if close is not None:
                close()

    for result, stage in (
        (weather_result, "weather"),
        (budget_result, "budget"),
        (places_result, "places"),
    ):
        if error := _provider_error(result, stage):
            raise error

    try:
        weather = WeatherReport.model_validate(weather_result)
    except PydanticValidationError:
        raise ProviderError("weather_unavailable") from None
    try:
        budget = BudgetReport.model_validate(budget_result)
        places = TypeAdapter(list[PlaceSuggestion]).validate_python(places_result)
    except PydanticValidationError:
        raise ProviderError("invalid_provider_response") from None

    selected_names = {place.name.casefold() for place in list_places(db, trip) if place.selected}
    profile = trip.planning_profile
    if profile is None:
        profile = TripPlanningProfile(trip_id=trip.id, departure_city=departure_city)
        trip.planning_profile = profile

    profile.departure_city = departure_city
    profile.weather_report = weather.model_dump(mode="json")
    profile.budget_report = budget.model_dump(mode="json")
    profile.weather_source = weather.source
    profile.budget_model = active_planning_provider.model
    profile.analyzed_at = utc_now()
    trip.weather_score = None
    trip.weather_rating = None
    trip.weather_summary = weather.summary
    trip.estimated_cost_min = budget.total.minimum
    trip.estimated_cost = budget.total.typical
    trip.estimated_cost_max = budget.total.maximum
    trip.status = TripStatus.READY.value

    db.execute(delete(Place).where(Place.trip_id == trip.id))
    created_places = [
        Place(
            trip_id=trip.id,
            name=suggestion.name,
            description=suggestion.description,
            latitude=suggestion.latitude,
            longitude=suggestion.longitude,
            recommended_days=suggestion.recommended_days,
            estimated_food=Decimal("0"),
            estimated_transport=Decimal("0"),
            estimated_tickets=Decimal("0"),
            estimated_activity=Decimal("0"),
            estimated_stay=Decimal("0"),
            weather_score=suggestion.relevance_score,
            overall_score=suggestion.relevance_score,
            best_for=suggestion.best_for,
            selected=suggestion.name.casefold() in selected_names,
        )
        for suggestion in places
    ]
    db.add_all(created_places)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return _persisted_response(db, trip)


def get_analysis(db: Session, trip: Trip) -> AnalysisResponse:
    return _persisted_response(db, trip)


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
