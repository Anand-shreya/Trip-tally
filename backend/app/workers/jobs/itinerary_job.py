from app.services.itinerary_service import run_itinerary_job


def perform(job_id: str) -> None:
    run_itinerary_job(job_id)
