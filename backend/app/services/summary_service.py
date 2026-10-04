from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, Trip
from app.providers.ai import generate_summary_text
from app.schemas.common import money
from app.schemas.summary import TripSummary
from app.services.settlement_service import calculate_balances, calculate_settlements


def build_summary(db: Session, trip: Trip) -> TripSummary:
    category_rows = db.execute(
        select(Expense.category, func.sum(Expense.base_amount))
        .where(Expense.trip_id == trip.id)
        .group_by(Expense.category)
    ).all()
    categories = {category: money(total) for category, total in category_rows}
    total = money(sum(categories.values(), Decimal("0")))
    remaining = money(trip.budget - total) if trip.budget is not None else None
    top_category = max(categories, key=categories.get) if categories else None
    top_expense = db.scalar(
        select(Expense)
        .where(Expense.trip_id == trip.id)
        .order_by(Expense.base_amount.desc())
        .limit(1)
    )
    balances = calculate_balances(db, trip)
    settlements = calculate_settlements(balances)
    narrative = generate_summary_text(
        budget=trip.budget,
        total_spent=total,
        top_category=top_category,
        currency=trip.base_currency,
    )
    return TripSummary(
        trip_id=trip.id,
        trip_name=trip.name,
        destination=trip.destination,
        days=trip.number_of_days,
        currency=trip.base_currency,
        budget=trip.budget,
        total_spent=total,
        remaining=remaining,
        average_per_day=money(total / max(1, trip.number_of_days)),
        categories=categories,
        most_expensive_category=top_category,
        most_expensive_expense=top_expense.description if top_expense else None,
        traveler_balances=balances,
        settlements=settlements,
        ai_summary=narrative,
    )
