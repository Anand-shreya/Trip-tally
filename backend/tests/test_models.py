from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import inspect, select


def test_trip_uses_uuid_and_exact_decimal_money(db):
    from app.models import Trip, User

    user = User(name="Demo", email="demo@tripwise.local")
    db.add(user)
    db.flush()
    trip = Trip(
        user_id=user.id,
        name="Coastal escape",
        destination="Sri Lanka",
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 11),
        number_of_days=7,
        base_currency="INR",
        budget=Decimal("80000.10"),
        travel_style="COMFORTABLE",
        status="DRAFT",
    )
    db.add(trip)
    db.commit()

    stored = db.scalar(select(Trip).where(Trip.id == trip.id))
    assert UUID(stored.id)
    assert stored.budget == Decimal("80000.10")
    assert stored.end_date == date(2026, 9, 11)


def test_deleting_trip_cascades_to_travelers_and_expenses(db):
    from app.models import Expense, ExpenseSplit, Traveler, Trip, User

    user = User(name="Demo", email="demo@tripwise.local")
    trip = Trip(
        user=user,
        name="Test",
        destination="Goa",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 2),
        number_of_days=2,
        base_currency="INR",
        travel_style="BUDGET",
        status="DRAFT",
    )
    traveler = Traveler(trip=trip, name="Shreya")
    expense = Expense(
        trip=trip,
        description="Lunch",
        amount=Decimal("500.00"),
        currency="INR",
        exchange_rate=Decimal("1"),
        base_amount=Decimal("500.00"),
        category="FOOD",
        paid_by_traveler=traveler,
        expense_date=date(2026, 1, 1),
        request_hash="hash",
        idempotency_key="key",
    )
    expense.splits.append(ExpenseSplit(traveler=traveler, share_amount=Decimal("500.00")))
    db.add(trip)
    db.commit()

    db.delete(trip)
    db.commit()

    assert db.scalar(select(Traveler)) is None
    assert db.scalar(select(Expense)) is None
    assert db.scalar(select(ExpenseSplit)) is None


def test_schema_has_unique_trip_idempotency_index(db):
    indexes = inspect(db.bind).get_indexes("expenses")
    unique_columns = {tuple(index["column_names"]) for index in indexes if index["unique"]}
    assert ("trip_id", "idempotency_key") in unique_columns


def test_deleting_trip_cascades_to_planning_profile(db):
    from app.models import Trip, TripPlanningProfile, User

    user = User(name="Demo", email="profile@example.test")
    trip = Trip(
        user=user,
        name="Profile test",
        destination="Kyoto",
        start_date=date(2027, 4, 4),
        end_date=date(2027, 4, 8),
        number_of_days=5,
        base_currency="INR",
        travel_style="COMFORTABLE",
        status="PLANNING",
    )
    trip.planning_profile = TripPlanningProfile(departure_city="Delhi")
    db.add(trip)
    db.commit()
    trip_id = trip.id

    db.delete(trip)
    db.commit()

    assert db.get(TripPlanningProfile, trip_id) is None
