from collections.abc import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import JobStatus, JobType
from app.core.exceptions import NotFoundError, ValidationError
from app.db.database import SessionLocal
from app.models import ItineraryActivity, ItineraryDay, Job, Place, Trip
from app.providers.ai import generate_itinerary
from app.schemas.itinerary import ItineraryPlan

Generator = Callable[[Trip, list[Place]], ItineraryPlan]


def get_itinerary(db: Session, trip: Trip) -> list[ItineraryDay]:
    return list(
        db.scalars(
            select(ItineraryDay)
            .where(ItineraryDay.trip_id == trip.id)
            .options(selectinload(ItineraryDay.activities))
            .order_by(ItineraryDay.day_number)
        ).unique()
    )


def replace_itinerary(db: Session, trip: Trip, plan: ItineraryPlan) -> list[ItineraryDay]:
    if len(plan.days) != trip.number_of_days:
        raise ValidationError(f"Itinerary must contain exactly {trip.number_of_days} days")
    expected_days = list(range(1, trip.number_of_days + 1))
    if [day.day for day in plan.days] != expected_days:
        raise ValidationError("Itinerary day numbers must be consecutive")
    expected_dates = [
        trip.start_date.fromordinal(trip.start_date.toordinal() + index)
        for index in range(trip.number_of_days)
    ]
    if [day.date for day in plan.days] != expected_dates:
        raise ValidationError("Itinerary dates must match the trip dates")

    rows = [
        ItineraryDay(
            trip_id=trip.id,
            day_number=day.day,
            date=day.date,
            title=day.title,
            summary=day.summary,
            activities=[
                ItineraryActivity(
                    title=activity.title,
                    description=activity.description,
                    activity_type=activity.activity_type,
                    start_time=activity.start_time,
                    end_time=activity.end_time,
                    location_name=activity.location_name,
                    latitude=activity.latitude,
                    longitude=activity.longitude,
                    estimated_cost=activity.estimated_cost,
                )
                for activity in day.activities
            ],
        )
        for day in plan.days
    ]
    try:
        db.execute(delete(ItineraryDay).where(ItineraryDay.trip_id == trip.id))
        db.add_all(rows)
        db.commit()
        return get_itinerary(db, trip)
    except Exception:
        db.rollback()
        raise


def enqueue_itinerary(db: Session, trip: Trip, *, dispatch: bool = True) -> Job:
    selected = list(
        db.scalars(select(Place).where(Place.trip_id == trip.id, Place.selected.is_(True)))
    )
    if not selected:
        raise ValidationError("Select at least one place before generating an itinerary")
    job = Job(
        trip_id=trip.id,
        type=JobType.GENERATE_ITINERARY.value,
        status=JobStatus.PENDING.value,
        attempt=0,
        max_attempts=3,
        payload={"place_ids": [place.id for place in selected]},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if dispatch:
        from app.workers.queue import dispatch_itinerary

        dispatch_itinerary(job.id, db=db)
        db.refresh(job)
    return job


def get_job(db: Session, job_id: str, trip_id: str | None = None) -> Job:
    statement = select(Job).where(Job.id == job_id)
    if trip_id:
        statement = statement.where(Job.trip_id == trip_id)
    job = db.scalar(statement)
    if job is None:
        raise NotFoundError("Job not found")
    return job


def run_itinerary_job(
    job_id: str, *, db: Session | None = None, generator: Generator | None = None
) -> Job:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        job = get_job(session, job_id)
        if job.status == JobStatus.SUCCESS.value:
            return job
        job.attempt += 1
        job.status = JobStatus.RUNNING.value
        job.error = None
        session.commit()
        trip = session.scalar(
            select(Trip).where(Trip.id == job.trip_id).options(selectinload(Trip.places))
        )
        selected = [place for place in trip.places if place.selected]
        plan = (generator or generate_itinerary)(trip, selected)
        days = replace_itinerary(session, trip, plan)
        job = get_job(session, job_id)
        job.status = JobStatus.SUCCESS.value
        job.result = {"days": len(days)}
        session.commit()
        return job
    except Exception as exc:
        session.rollback()
        job = get_job(session, job_id)
        job.status = (
            JobStatus.DEAD.value if job.attempt >= job.max_attempts else JobStatus.RETRY.value
        )
        job.error = str(exc)
        session.commit()
        return job
    finally:
        if owns_session:
            session.close()
