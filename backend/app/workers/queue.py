from sqlalchemy.orm import Session

from app.core.config import get_settings


def dispatch_itinerary(job_id: str, *, db: Session | None = None) -> None:
    settings = get_settings()
    if settings.queue_mode == "redis":
        from redis import Redis
        from rq import Queue, Retry

        queue = Queue("tripwise", connection=Redis.from_url(settings.redis_url))
        queue.enqueue(
            "app.workers.jobs.itinerary_job.perform",
            job_id,
            job_timeout=300,
            retry=Retry(max=2, interval=[5, 15]),
        )
        return
    from app.services.itinerary_service import run_itinerary_job

    run_itinerary_job(job_id, db=db)
