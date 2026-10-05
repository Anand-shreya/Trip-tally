from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@pytest.mark.asyncio
async def test_demo_seed_is_idempotent_and_builds_a_complete_trip(db: Session):
    from app.models import Expense, ItineraryDay, Place, Traveler, Trip, User
    from app.schemas.planning import (
        BudgetCategories,
        BudgetReport,
        CurrentWeather,
        DailyWeather,
        EstimateRange,
        PlaceSuggestion,
        ResolvedLocation,
        WeatherReport,
    )
    from app.seed import DEMO_TRIP_NAME, seed_demo

    async def weather_fetcher(*_args):
        return WeatherReport(
            location=ResolvedLocation(
                name="Kerala",
                country_code="IN",
                latitude=10.85,
                longitude=76.27,
                timezone_offset_seconds=19800,
            ),
            current=CurrentWeather(
                observed_at=datetime(2026, 10, 5, 12, tzinfo=UTC),
                condition="Clouds",
                description="scattered clouds",
                temperature_c=27,
                feels_like_c=29,
                minimum_c=24,
                maximum_c=30,
                humidity_percent=72,
                pressure_hpa=1010,
                visibility_m=10000,
                cloud_percent=40,
                wind_speed_kph=9,
                wind_direction_degrees=210,
                sunrise_at=datetime(2026, 10, 5, 1, tzinfo=UTC),
                sunset_at=datetime(2026, 10, 5, 13, tzinfo=UTC),
            ),
            daily=[
                DailyWeather(
                    requested_date=date(2027, 2, 14),
                    source_date=date(2026, 2, 14),
                    source="historical",
                    minimum_c=23,
                    maximum_c=31,
                    representative_c=27,
                    condition="Partly cloudy",
                    precipitation_mm=1,
                    maximum_wind_kph=12,
                )
            ],
            source="openweather+open-meteo",
            summary="Current conditions in Kerala: scattered clouds, 27°C.",
        )

    class SeedPlanningProvider:
        model = "test-gemini"

        async def estimate_budget(self, facts):
            categories = BudgetCategories(
                flights=EstimateRange(minimum=18000, typical=24000, maximum=32000),
                accommodation=EstimateRange(minimum=12000, typical=18000, maximum=26000),
                food=EstimateRange(minimum=6000, typical=9000, maximum=14000),
                local_transport=EstimateRange(minimum=5000, typical=8000, maximum=12000),
                tickets=EstimateRange(minimum=2000, typical=3500, maximum=6000),
                activities=EstimateRange(minimum=4000, typical=7000, maximum=11000),
            )
            ranges = list(categories.model_dump().values())
            return BudgetReport(
                currency=facts.currency,
                traveler_count=facts.traveler_count,
                number_of_days=facts.number_of_days,
                categories=categories,
                total=EstimateRange(
                    minimum=sum(item["minimum"] for item in ranges),
                    typical=sum(item["typical"] for item in ranges),
                    maximum=sum(item["maximum"] for item in ranges),
                ),
            )

        async def discover_places(self, _facts):
            return [
                PlaceSuggestion(
                    name=name,
                    description=f"Explore {name}.",
                    latitude=latitude,
                    longitude=longitude,
                    recommended_days=Decimal("1"),
                    best_for=["Nature"],
                    relevance_score=score,
                )
                for name, latitude, longitude, score in (
                    ("Alappuzha", 9.49, 76.33, Decimal("9.6")),
                    ("Munnar", 10.09, 77.06, Decimal("9.3")),
                    ("Fort Kochi", 9.97, 76.24, Decimal("9.0")),
                )
            ]

    provider = SeedPlanningProvider()
    first_trip_id = await seed_demo(
        db,
        weather_fetcher=weather_fetcher,
        planning_provider=provider,
    )
    second_trip_id = await seed_demo(
        db,
        weather_fetcher=weather_fetcher,
        planning_provider=provider,
    )

    assert second_trip_id == first_trip_id
    trip = db.scalar(select(Trip).where(Trip.id == first_trip_id))
    assert trip is not None
    assert trip.name == DEMO_TRIP_NAME
    assert trip.departure_city == "Bengaluru"
    assert trip.weather_score is None
    assert trip.planning_profile.weather_report is not None
    assert trip.estimated_cost is not None
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert db.scalar(select(func.count()).select_from(Trip)) == 1
    assert (
        db.scalar(select(func.count()).select_from(Traveler).where(Traveler.trip_id == trip.id))
        == 3
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(Place)
            .where(Place.trip_id == trip.id, Place.selected.is_(True))
        )
        >= 2
    )
    assert (
        db.scalar(
            select(func.count()).select_from(ItineraryDay).where(ItineraryDay.trip_id == trip.id)
        )
        == trip.number_of_days
    )
    assert (
        db.scalar(select(func.count()).select_from(Expense).where(Expense.trip_id == trip.id)) >= 3
    )
