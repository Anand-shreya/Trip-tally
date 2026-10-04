import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@pytest.mark.asyncio
async def test_demo_seed_is_idempotent_and_builds_a_complete_trip(db: Session):
    from app.models import Expense, ItineraryDay, Place, Traveler, Trip, User
    from app.seed import DEMO_TRIP_NAME, seed_demo

    first_trip_id = await seed_demo(db)
    second_trip_id = await seed_demo(db)

    assert second_trip_id == first_trip_id
    trip = db.scalar(select(Trip).where(Trip.id == first_trip_id))
    assert trip is not None
    assert trip.name == DEMO_TRIP_NAME
    assert trip.weather_score is not None
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
