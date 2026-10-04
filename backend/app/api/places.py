from fastapi import APIRouter

from app.api.deps import DbSession, OwnedTrip
from app.schemas.place import PlaceRead, PlaceSelection
from app.services.planning_service import list_places, select_places


router = APIRouter(prefix="/trips/{trip_id}/places", tags=["places"])


@router.get("", response_model=list[PlaceRead])
def list_places_route(trip: OwnedTrip, db: DbSession):
    return list_places(db, trip)


@router.post("/select", response_model=list[PlaceRead])
def select_places_route(payload: PlaceSelection, trip: OwnedTrip, db: DbSession):
    return select_places(db, trip, payload.place_ids)

