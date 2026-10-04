import hashlib
import json
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import SplitType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Expense, ExpenseSplit, Traveler, Trip
from app.providers.currency import REFERENCE_TO_INR, convert
from app.schemas.common import money
from app.schemas.expense import ExpenseCreate


def _request_hash(payload: ExpenseCreate) -> str:
    canonical = json.dumps(
        payload.model_dump(mode="json", warnings="none"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _exchange_rate(source: str, target: str) -> Decimal:
    if source == target:
        return Decimal("1")
    if source not in REFERENCE_TO_INR or target not in REFERENCE_TO_INR:
        raise ValidationError(f"No exchange rate is available for {source}/{target}")
    return (REFERENCE_TO_INR[source] / REFERENCE_TO_INR[target]).quantize(Decimal("0.000001"))


def _load_trip_travelers(db: Session, trip: Trip, ids: set[str]) -> dict[str, Traveler]:
    travelers = list(
        db.scalars(select(Traveler).where(Traveler.trip_id == trip.id, Traveler.id.in_(ids)))
    )
    return {traveler.id: traveler for traveler in travelers}


def _equal_shares(base_amount: Decimal, traveler_ids: list[str]) -> list[tuple[str, Decimal]]:
    count = len(traveler_ids)
    raw = (base_amount / count).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    cents = int((base_amount - raw * count) * 100)
    return [
        (traveler_id, raw + (Decimal("0.01") if index < cents else Decimal("0")))
        for index, traveler_id in enumerate(traveler_ids)
    ]


def _custom_shares(payload: ExpenseCreate, base_amount: Decimal) -> list[tuple[str, Decimal]]:
    included = payload.included_travelers
    split_ids = [split.traveler_id for split in payload.splits]
    if len(set(included)) != len(included):
        raise ValidationError("Included travelers must be unique")
    if len(set(split_ids)) != len(split_ids):
        raise ValidationError("Custom split travelers must be unique")
    if set(split_ids) != set(included):
        raise ValidationError("Every included traveler must have exactly one custom share")
    shares = [(split.traveler_id, money(split.amount)) for split in payload.splits]
    if any(amount < 0 for _, amount in shares):
        raise ValidationError("Custom shares cannot be negative")
    if sum((amount for _, amount in shares), Decimal("0")) != base_amount:
        raise ValidationError("Custom shares must equal the expense base amount")
    return shares


def create_expense(
    db: Session, trip: Trip, payload: ExpenseCreate, idempotency_key: str
) -> Expense:
    request_hash = _request_hash(payload)
    existing = db.scalar(
        select(Expense)
        .where(Expense.trip_id == trip.id, Expense.idempotency_key == idempotency_key)
        .options(selectinload(Expense.splits))
    )
    if existing:
        if existing.request_hash != request_hash:
            raise ConflictError("Idempotency key was already used for a different expense")
        return existing

    included = payload.included_travelers
    required_ids = set(included) | {payload.paid_by}
    travelers = _load_trip_travelers(db, trip, required_ids)
    if payload.paid_by not in travelers:
        raise ValidationError("The expense payer does not belong to this trip")
    if len(set(included)) != len(included) or any(item not in travelers for item in included):
        raise ValidationError("Every included traveler must belong to this trip and be unique")

    rate = _exchange_rate(payload.currency, trip.base_currency)
    base_amount = convert(payload.amount, rate)
    shares = (
        _equal_shares(base_amount, included)
        if payload.split_type == SplitType.EQUAL
        else _custom_shares(payload, base_amount)
    )
    expense = Expense(
        trip_id=trip.id,
        description=payload.description,
        amount=money(payload.amount),
        currency=payload.currency,
        exchange_rate=rate,
        base_amount=base_amount,
        category=payload.category.value if hasattr(payload.category, "value") else payload.category,
        paid_by=payload.paid_by,
        expense_date=payload.expense_date,
        location=payload.location,
        notes=payload.notes,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        splits=[
            ExpenseSplit(traveler_id=traveler_id, share_amount=amount)
            for traveler_id, amount in shares
        ],
    )
    try:
        db.add(expense)
        db.commit()
        db.refresh(expense)
        _ = expense.splits
        return expense
    except Exception:
        db.rollback()
        raise


def list_expenses(
    db: Session,
    trip: Trip,
    *,
    category: str | None = None,
    traveler_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Expense]:
    statement = (
        select(Expense).where(Expense.trip_id == trip.id).options(selectinload(Expense.splits))
    )
    if category:
        statement = statement.where(Expense.category == category)
    if traveler_id:
        split_expenses = select(ExpenseSplit.expense_id).where(
            ExpenseSplit.traveler_id == traveler_id
        )
        statement = statement.where(
            or_(Expense.paid_by == traveler_id, Expense.id.in_(split_expenses))
        )
    if start_date:
        statement = statement.where(Expense.expense_date >= start_date)
    if end_date:
        statement = statement.where(Expense.expense_date <= end_date)
    statement = statement.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    return list(db.scalars(statement).unique())


def delete_expense(db: Session, trip: Trip, expense_id: str) -> None:
    expense = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.trip_id == trip.id))
    if expense is None:
        raise NotFoundError("Expense not found")
    db.delete(expense)
    db.commit()
