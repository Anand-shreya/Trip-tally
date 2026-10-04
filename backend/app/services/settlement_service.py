from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseSplit, Traveler, Trip
from app.schemas.common import money
from app.schemas.expense import Settlement, TravelerBalance


def calculate_balances(db: Session, trip: Trip) -> list[TravelerBalance]:
    travelers = list(
        db.scalars(
            select(Traveler).where(Traveler.trip_id == trip.id).order_by(Traveler.created_at)
        )
    )
    balances: list[TravelerBalance] = []
    for traveler in travelers:
        paid = db.scalar(
            select(func.coalesce(func.sum(Expense.base_amount), 0)).where(
                Expense.trip_id == trip.id, Expense.paid_by == traveler.id
            )
        )
        owed = db.scalar(
            select(func.coalesce(func.sum(ExpenseSplit.share_amount), 0))
            .join(Expense, Expense.id == ExpenseSplit.expense_id)
            .where(Expense.trip_id == trip.id, ExpenseSplit.traveler_id == traveler.id)
        )
        paid_money = money(paid or 0)
        owed_money = money(owed or 0)
        balances.append(
            TravelerBalance(
                traveler_id=traveler.id,
                traveler=traveler.name,
                paid=paid_money,
                owed=owed_money,
                net=money(paid_money - owed_money),
            )
        )
    return balances


def calculate_settlements(balances: list[TravelerBalance]) -> list[Settlement]:
    creditors = sorted(
        [dict(item.model_dump()) for item in balances if item.net > 0],
        key=lambda item: (-item["net"], item["traveler_id"]),
    )
    debtors = sorted(
        [dict(item.model_dump()) for item in balances if item.net < 0],
        key=lambda item: (item["net"], item["traveler_id"]),
    )
    settlements: list[Settlement] = []
    creditor_index = 0
    debtor_index = 0
    while creditor_index < len(creditors) and debtor_index < len(debtors):
        creditor = creditors[creditor_index]
        debtor = debtors[debtor_index]
        amount = money(min(creditor["net"], abs(debtor["net"])))
        if amount > 0:
            settlements.append(
                Settlement(
                    from_traveler_id=debtor["traveler_id"],
                    from_traveler=debtor["traveler"],
                    to_traveler_id=creditor["traveler_id"],
                    to_traveler=creditor["traveler"],
                    amount=amount,
                )
            )
        creditor["net"] = money(creditor["net"] - amount)
        debtor["net"] = money(debtor["net"] + amount)
        if creditor["net"] == 0:
            creditor_index += 1
        if debtor["net"] == 0:
            debtor_index += 1
    return settlements
