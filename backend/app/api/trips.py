from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUserId, DbSession, OwnedTrip
from app.schemas.place import AnalysisResponse
from app.schemas.trip import TravelerCreate, TravelerRead, TripCreate, TripCreated, TripRead
from app.services.planning_service import analyze_trip
from app.services.trip_service import (
    add_traveler,
    create_trip,
    delete_traveler,
    delete_trip,
    list_travelers,
    list_trips,
)

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("", response_model=TripCreated, status_code=status.HTTP_201_CREATED)
def create_trip_route(payload: TripCreate, db: DbSession, user_id: CurrentUserId) -> TripCreated:
    trip = create_trip(db, user_id, payload)
    return TripCreated(trip_id=trip.id, status=trip.status)


@router.get("", response_model=list[TripRead])
def list_trips_route(db: DbSession, user_id: CurrentUserId):
    return list_trips(db, user_id)


@router.get("/{trip_id}", response_model=TripRead)
def get_trip_route(trip: OwnedTrip):
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip_route(trip: OwnedTrip, db: DbSession) -> Response:
    delete_trip(db, trip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{trip_id}/travelers", response_model=TravelerRead, status_code=status.HTTP_201_CREATED
)
def add_traveler_route(payload: TravelerCreate, trip: OwnedTrip, db: DbSession):
    return add_traveler(db, trip, payload)


@router.get("/{trip_id}/travelers", response_model=list[TravelerRead])
def list_travelers_route(trip: OwnedTrip, db: DbSession):
    return list_travelers(db, trip)


@router.delete("/{trip_id}/travelers/{traveler_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_traveler_route(traveler_id: str, trip: OwnedTrip, db: DbSession) -> Response:
    delete_traveler(db, trip, traveler_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{trip_id}/analyze", response_model=AnalysisResponse)
async def analyze_trip_route(trip: OwnedTrip, db: DbSession):
    return await analyze_trip(db, trip)
