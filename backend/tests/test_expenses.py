from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select


def expense_trip(db):
    from app.models import Traveler, Trip, User

    user = User(name="Owner", email="expenses@tripwise.local")
    trip = Trip(
        user=user,
        name="Goa",
        destination="Goa",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 3),
        number_of_days=3,
        base_currency="INR",
        budget=Decimal("10000"),
        travel_style="COMFORTABLE",
        status="READY",
    )
    trip.travelers = [Traveler(name=name) for name in ["Shreya", "Rahul", "Amit"]]
    db.add(trip)
    db.commit()
    return trip


def equal_payload(trip, amount="100.00", description="Dinner"):
    from app.schemas.expense import ExpenseCreate

    return ExpenseCreate(
        description=description,
        amount=Decimal(amount),
        currency="INR",
        category="FOOD",
        paid_by=trip.travelers[0].id,
        expense_date=date(2026, 1, 2),
        included_travelers=[traveler.id for traveler in trip.travelers],
        split_type="EQUAL",
    )


def test_equal_split_assigns_remainder_cents_and_preserves_total(db):
    from app.services.expense_service import create_expense

    trip = expense_trip(db)
    expense = create_expense(db, trip, equal_payload(trip), "equal-1")

    assert [split.share_amount for split in expense.splits] == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert sum(split.share_amount for split in expense.splits) == expense.base_amount


def test_custom_split_persists_explicit_shares(db):
    from app.schemas.expense import CustomSplit, ExpenseCreate
    from app.services.expense_service import create_expense

    trip = expense_trip(db)
    payload = ExpenseCreate(
        description="Rooms",
        amount=Decimal("3000"),
        currency="INR",
        category="ACCOMMODATION",
        paid_by=trip.travelers[1].id,
        expense_date=date(2026, 1, 2),
        included_travelers=[traveler.id for traveler in trip.travelers],
        split_type="CUSTOM",
        splits=[
            CustomSplit(traveler_id=trip.travelers[0].id, amount=Decimal("1500")),
            CustomSplit(traveler_id=trip.travelers[1].id, amount=Decimal("1000")),
            CustomSplit(traveler_id=trip.travelers[2].id, amount=Decimal("500")),
        ],
    )

    expense = create_expense(db, trip, payload, "custom-1")
    assert [split.share_amount for split in expense.splits] == [
        Decimal("1500.00"),
        Decimal("1000.00"),
        Decimal("500.00"),
    ]


@pytest.mark.parametrize("case", ["mismatch", "duplicate", "negative", "omitted"])
def test_custom_split_rejects_invalid_share_sets_without_partial_expense(db, case):
    from app.core.exceptions import ValidationError
    from app.schemas.expense import CustomSplit, ExpenseCreate
    from app.services.expense_service import create_expense

    trip = expense_trip(db)
    ids = [traveler.id for traveler in trip.travelers]
    splits = [
        CustomSplit(traveler_id=ids[0], amount=Decimal("40")),
        CustomSplit(traveler_id=ids[1], amount=Decimal("30")),
        CustomSplit(traveler_id=ids[2], amount=Decimal("30")),
    ]
    included = ids[:]
    if case == "mismatch":
        splits[2] = CustomSplit(traveler_id=ids[2], amount=Decimal("20"))
    elif case == "duplicate":
        splits[2] = CustomSplit(traveler_id=ids[1], amount=Decimal("30"))
    elif case == "negative":
        splits[2] = CustomSplit(traveler_id=ids[2], amount=Decimal("-1"))
    else:
        splits = splits[:2]

    payload = ExpenseCreate.model_construct(
        description="Invalid",
        amount=Decimal("100"),
        currency="INR",
        category="FOOD",
        paid_by=ids[0],
        expense_date=date(2026, 1, 2),
        included_travelers=included,
        split_type="CUSTOM",
        splits=splits,
        location=None,
        notes=None,
    )
    with pytest.raises(ValidationError):
        create_expense(db, trip, payload, f"invalid-{case}")

    from app.models import Expense, ExpenseSplit

    assert db.scalar(select(func.count(Expense.id))) == 0
    assert db.scalar(select(func.count(ExpenseSplit.id))) == 0


def test_expense_rejects_payer_from_another_trip(db):
    from app.core.exceptions import ValidationError
    from app.models import Traveler, Trip
    from app.services.expense_service import create_expense

    trip = expense_trip(db)
    other = Trip(
        user_id=trip.user_id,
        name="Other",
        destination="Delhi",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 1),
        number_of_days=1,
        base_currency="INR",
        travel_style="BUDGET",
        status="READY",
    )
    outsider = Traveler(name="Outsider", trip=other)
    db.add(other)
    db.commit()
    payload = equal_payload(trip)
    payload.paid_by = outsider.id

    with pytest.raises(ValidationError, match="payer"):
        create_expense(db, trip, payload, "foreign-payer")


def test_idempotency_replays_same_request_and_conflicts_on_changed_request(db):
    from app.core.exceptions import ConflictError
    from app.services.expense_service import create_expense

    trip = expense_trip(db)
    original = create_expense(db, trip, equal_payload(trip), "stable-key")
    replay = create_expense(db, trip, equal_payload(trip), "stable-key")
    assert replay.id == original.id

    with pytest.raises(ConflictError):
        create_expense(db, trip, equal_payload(trip, description="Taxi"), "stable-key")


def test_simultaneous_idempotent_requests_return_the_committed_expense(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, selectinload

    from app.db.database import Base
    from app.models import Trip
    from app.services.expense_service import create_expense

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        trip = expense_trip(session)
        payload = equal_payload(trip)
        original_commit = session.commit
        competing_expense_id = None
        race_started = False

        def racing_commit():
            nonlocal competing_expense_id, race_started
            if not race_started:
                race_started = True
                with Session(engine) as competitor:
                    competing_trip = competitor.scalar(
                        select(Trip).where(Trip.id == trip.id).options(selectinload(Trip.travelers))
                    )
                    competing = create_expense(
                        competitor, competing_trip, payload, "simultaneous-key"
                    )
                    competing_expense_id = competing.id
            original_commit()

        monkeypatch.setattr(session, "commit", racing_commit)
        replay = create_expense(session, trip, payload, "simultaneous-key")

        assert replay.id == competing_expense_id


def test_list_expenses_filters_category_traveler_and_dates(db):
    from app.services.expense_service import create_expense, list_expenses

    trip = expense_trip(db)
    create_expense(db, trip, equal_payload(trip, description="Dinner"), "one")
    taxi = equal_payload(trip, description="Taxi")
    taxi.category = "TRANSPORT"
    taxi.included_travelers = [trip.travelers[1].id, trip.travelers[2].id]
    create_expense(db, trip, taxi, "two")

    assert [item.description for item in list_expenses(db, trip, category="FOOD")] == ["Dinner"]
    assert [
        item.description for item in list_expenses(db, trip, traveler_id=trip.travelers[2].id)
    ] == [
        "Taxi",
        "Dinner",
    ]
    assert list_expenses(db, trip, start_date=date(2026, 1, 3)) == []
