from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession, OwnedTrip
from app.schemas.itinerary import ItineraryDayRead, JobRead
from app.services.itinerary_service import enqueue_itinerary, get_itinerary, get_job
from app.services.trip_service import get_trip

router = APIRouter(tags=["itinerary"])


@router.post(
    "/trips/{trip_id}/itinerary/generate",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_itinerary_route(trip: OwnedTrip, db: DbSession):
    return enqueue_itinerary(db, trip)


@router.get("/trips/{trip_id}/itinerary", response_model=list[ItineraryDayRead])
def get_itinerary_route(trip: OwnedTrip, db: DbSession):
    return get_itinerary(db, trip)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job_route(job_id: str, db: DbSession, user_id: CurrentUserId):
    job = get_job(db, job_id)
    get_trip(db, job.trip_id, user_id)
    return job
