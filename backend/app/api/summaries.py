from fastapi import APIRouter

from app.api.deps import DbSession, OwnedTrip
from app.schemas.expense import BalancesResponse, SettlementsResponse
from app.schemas.summary import TripSummary
from app.services.settlement_service import calculate_balances, calculate_settlements
from app.services.summary_service import build_summary


router = APIRouter(prefix="/trips/{trip_id}", tags=["summary"])


@router.get("/balances", response_model=BalancesResponse)
def balances_route(trip: OwnedTrip, db: DbSession) -> BalancesResponse:
    return BalancesResponse(balances=calculate_balances(db, trip))


@router.get("/settlements", response_model=SettlementsResponse)
def settlements_route(trip: OwnedTrip, db: DbSession) -> SettlementsResponse:
    balances = calculate_balances(db, trip)
    return SettlementsResponse(settlements=calculate_settlements(balances))


@router.get("/summary", response_model=TripSummary)
def summary_route(trip: OwnedTrip, db: DbSession):
    return build_summary(db, trip)

