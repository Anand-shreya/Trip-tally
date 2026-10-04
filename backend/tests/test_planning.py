from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError


def make_user(db, email="owner@tripwise.local"):
    from app.models import User

    user = User(name="Owner", email=email)
    db.add(user)
    db.commit()
    return user


def test_create_trip_derives_inclusive_end_date_and_normalizes_currency(db):
    from app.schemas.trip import TripCreate
    from app.services.trip_service import create_trip

    user = make_user(db)
    payload = TripCreate(
        name="Island loop",
        destination="Sri Lanka",
        start_date=date(2026, 9, 5),
        number_of_days=7,
        budget=Decimal("80000"),
        currency="inr",
        travel_style="COMFORTABLE",
    )

    trip = create_trip(db, user.id, payload)

    assert trip.end_date == date(2026, 9, 11)
    assert trip.base_currency == "INR"
    assert trip.status == "PLANNING"


@pytest.mark.parametrize(
    ("field", "value"),
    [("number_of_days", 0), ("budget", Decimal("-0.01")), ("currency", "RUPEE")],
)
def test_trip_request_rejects_invalid_values(field, value):
    from app.schemas.trip import TripCreate

    data = {
        "name": "Trip",
        "destination": "Goa",
        "start_date": date(2026, 1, 1),
        "number_of_days": 2,
        "budget": Decimal("1000"),
        "currency": "INR",
        "travel_style": "BUDGET",
    }
    data[field] = value
    with pytest.raises(PydanticValidationError):
        TripCreate(**data)


def test_trip_lookup_hides_another_users_trip(db):
    from app.core.exceptions import NotFoundError
    from app.schemas.trip import TripCreate
    from app.services.trip_service import create_trip, get_trip

    owner = make_user(db)
    stranger = make_user(db, "stranger@tripwise.local")
    trip = create_trip(
        db,
        owner.id,
        TripCreate(
            name="Private",
            destination="Goa",
            start_date=date(2026, 1, 1),
            number_of_days=2,
            currency="INR",
            travel_style="BUDGET",
        ),
    )

    with pytest.raises(NotFoundError):
        get_trip(db, trip.id, stranger.id)


@pytest.mark.asyncio
async def test_analysis_is_deterministic_and_scores_are_bounded(db):
    from app.schemas.trip import TripCreate
    from app.services.planning_service import analyze_trip
    from app.services.trip_service import create_trip

    user = make_user(db)
    trip = create_trip(
        db,
        user.id,
        TripCreate(
            name="Island loop",
            destination="Sri Lanka",
            start_date=date(2026, 9, 5),
            number_of_days=7,
            budget=Decimal("80000"),
            currency="INR",
            travel_style="COMFORTABLE",
        ),
    )

    first = await analyze_trip(db, trip)
    second = await analyze_trip(db, trip)

    assert first.weather.score == second.weather.score
    assert Decimal("0") <= first.weather.score <= Decimal("10")
    assert first.estimated_budget.minimum < first.estimated_budget.typical
    assert first.estimated_budget.typical < first.estimated_budget.maximum
    assert len(first.places) >= 5
    assert all(Decimal("0") <= place.overall_score <= Decimal("10") for place in first.places)


@pytest.mark.asyncio
async def test_select_places_rejects_place_from_another_trip(db):
    from app.core.exceptions import ValidationError
    from app.schemas.trip import TripCreate
    from app.services.planning_service import analyze_trip, select_places
    from app.services.trip_service import create_trip

    user = make_user(db)

    def payload(name):
        return TripCreate(
            name=name,
            destination="Sri Lanka",
            start_date=date(2026, 9, 5),
            number_of_days=4,
            currency="INR",
            travel_style="COMFORTABLE",
        )

    trip_a = create_trip(db, user.id, payload("A"))
    trip_b = create_trip(db, user.id, payload("B"))
    result_b = await analyze_trip(db, trip_b)

    with pytest.raises(ValidationError, match="do not belong"):
        select_places(db, trip_a, [result_b.places[0].id])


def test_traveler_name_is_trimmed_and_cannot_be_empty(db):
    from app.schemas.trip import TravelerCreate

    assert TravelerCreate(name="  Shreya  ").name == "Shreya"
    with pytest.raises(PydanticValidationError):
        TravelerCreate(name="   ")
