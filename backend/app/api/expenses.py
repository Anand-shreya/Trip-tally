from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.api.deps import DbSession, OwnedTrip
from app.schemas.expense import ExpenseCreate, ExpenseRead
from app.services.expense_service import create_expense, delete_expense, list_expenses

router = APIRouter(prefix="/trips/{trip_id}/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense_route(
    payload: ExpenseCreate,
    trip: OwnedTrip,
    db: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=100)],
):
    return create_expense(db, trip, payload, idempotency_key)


@router.get("", response_model=list[ExpenseRead])
def list_expenses_route(
    trip: OwnedTrip,
    db: DbSession,
    category: Annotated[str | None, Query()] = None,
    traveler_id: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
):
    return list_expenses(
        db,
        trip,
        category=category,
        traveler_id=traveler_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense_route(expense_id: str, trip: OwnedTrip, db: DbSession) -> Response:
    delete_expense(db, trip, expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
