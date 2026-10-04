from app.core.enums import JobStatus
from app.services.itinerary_service import run_itinerary_job


def perform(job_id: str) -> None:
    job = run_itinerary_job(job_id)
    if job.status == JobStatus.RETRY.value:
        raise RuntimeError(job.error or "Itinerary generation needs another attempt")
