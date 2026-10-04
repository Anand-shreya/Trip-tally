import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import ExpenseCategory, SplitType, TravelStyle
from app.db.database import SessionLocal, init_db
from app.models import Trip, User
from app.schemas.expense import ExpenseCreate
from app.schemas.trip import TravelerCreate, TripCreate
from app.services.expense_service import create_expense
from app.services.itinerary_service import enqueue_itinerary, run_itinerary_job
from app.services.planning_service import analyze_trip, list_places, select_places
from app.services.trip_service import add_traveler, create_trip

DEMO_TRIP_NAME = "Kerala Backwaters Escape"


async def seed_demo(db: Session) -> str:
    """Create the deterministic showcase trip once and return its ID."""
    settings = get_settings()
    user = db.get(User, settings.demo_user_id)
    if user is None:
        user = User(
            id=settings.demo_user_id,
            name=settings.demo_user_name,
            email=settings.demo_user_email,
        )
        db.add(user)
        db.commit()

    existing = db.scalar(
        select(Trip).where(Trip.user_id == settings.demo_user_id, Trip.name == DEMO_TRIP_NAME)
    )
    if existing is not None:
        return existing.id

    trip = create_trip(
        db,
        settings.demo_user_id,
        TripCreate(
            name=DEMO_TRIP_NAME,
            destination="Kerala",
            start_date=date(2027, 2, 14),
            number_of_days=5,
            budget=Decimal("75000"),
            currency="INR",
            travel_style=TravelStyle.COMFORTABLE,
        ),
    )
    travelers = [
        add_traveler(db, trip, TravelerCreate(name=name)) for name in ("Shreya", "Rahul", "Amit")
    ]

    await analyze_trip(db, trip)
    recommended = list_places(db, trip)[:3]
    select_places(db, trip, [place.id for place in recommended])
    job = enqueue_itinerary(db, trip, dispatch=False)
    run_itinerary_job(job.id, db=db)

    expenses = [
        (
            "Houseboat stay",
            "18000",
            ExpenseCategory.ACCOMMODATION,
            travelers[0].id,
            date(2027, 2, 14),
        ),
        ("Kerala sadya lunch", "2400", ExpenseCategory.FOOD, travelers[1].id, date(2027, 2, 15)),
        ("Munnar cab", "6200", ExpenseCategory.TRANSPORT, travelers[2].id, date(2027, 2, 16)),
    ]
    participant_ids = [traveler.id for traveler in travelers]
    for index, (description, amount, category, payer, expense_date) in enumerate(expenses, 1):
        create_expense(
            db,
            trip,
            ExpenseCreate(
                description=description,
                amount=Decimal(amount),
                currency="INR",
                category=category,
                paid_by=payer,
                expense_date=expense_date,
                included_travelers=participant_ids,
                split_type=SplitType.EQUAL,
            ),
            idempotency_key=f"demo-expense-{index}",
        )
    return trip.id


def main() -> None:
    init_db()
    with SessionLocal() as db:
        trip_id = asyncio.run(seed_demo(db))
    print(f"TripWise demo is ready (trip id: {trip_id})")


if __name__ == "__main__":
    main()
