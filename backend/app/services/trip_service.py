from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import TripStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Traveler, Trip, TripArchive, TripLocation, TripPlanningProfile
from app.schemas.trip import TravelerCreate, TripCreate


def create_trip(db: Session, user_id: str, payload: TripCreate) -> Trip:
    departure_city = (
        payload.departure_location.label if payload.departure_location else payload.departure_city
    )
    destination = (
        payload.destination_location.label if payload.destination_location else payload.destination
    )
    trip = Trip(
        user_id=user_id,
        name=payload.name,
        destination=destination,
        start_date=payload.start_date,
        end_date=payload.start_date + timedelta(days=payload.number_of_days - 1),
        number_of_days=payload.number_of_days,
        base_currency=payload.currency,
        budget=payload.budget,
        travel_style=payload.travel_style.value,
        status=TripStatus.PLANNING.value,
    )
    trip.planning_profile = TripPlanningProfile(departure_city=departure_city)
    for kind, selection in (
        ("departure", payload.departure_location),
        ("destination", payload.destination_location),
    ):
        if selection is not None:
            trip.locations.append(TripLocation(kind=kind, **selection.model_dump()))
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def list_trips(db: Session, user_id: str) -> list[Trip]:
    statement = (
        select(Trip)
        .where(Trip.user_id == user_id)
        .options(
            selectinload(Trip.travelers),
            selectinload(Trip.archive_record),
            selectinload(Trip.planning_profile),
            selectinload(Trip.locations),
        )
        .order_by(Trip.start_date.desc())
    )
    return list(db.scalars(statement).unique())


def get_trip(db: Session, trip_id: str, user_id: str) -> Trip:
    statement = (
        select(Trip)
        .where(Trip.id == trip_id, Trip.user_id == user_id)
        .options(
            selectinload(Trip.travelers),
            selectinload(Trip.places),
            selectinload(Trip.archive_record),
            selectinload(Trip.planning_profile),
            selectinload(Trip.locations),
        )
    )
    trip = db.scalar(statement)
    if trip is None:
        raise NotFoundError("Trip not found")
    return trip


def delete_trip(db: Session, trip: Trip) -> None:
    db.delete(trip)
    db.commit()


def archive_trip(db: Session, trip: Trip) -> Trip:
    if trip.archive_record is None:
        trip.archive_record = TripArchive()
        db.commit()
        db.refresh(trip)
    return trip


def restore_trip(db: Session, trip: Trip) -> Trip:
    if trip.archive_record is not None:
        trip.archive_record = None
        db.commit()
        db.refresh(trip)
    return trip


def add_traveler(db: Session, trip: Trip, payload: TravelerCreate) -> Traveler:
    existing = db.scalar(
        select(Traveler).where(Traveler.trip_id == trip.id, Traveler.name == payload.name)
    )
    if existing:
        raise ConflictError("A traveler with this name already exists")
    traveler = Traveler(
        trip_id=trip.id, name=payload.name, email=str(payload.email) if payload.email else None
    )
    db.add(traveler)
    db.commit()
    db.refresh(traveler)
    return traveler


def list_travelers(db: Session, trip: Trip) -> list[Traveler]:
    return list(
        db.scalars(
            select(Traveler).where(Traveler.trip_id == trip.id).order_by(Traveler.created_at)
        )
    )


def delete_traveler(db: Session, trip: Trip, traveler_id: str) -> None:
    traveler = db.scalar(
        select(Traveler).where(Traveler.id == traveler_id, Traveler.trip_id == trip.id)
    )
    if traveler is None:
        raise NotFoundError("Traveler not found")
    if traveler.paid_expenses or traveler.expense_splits:
        raise ConflictError("Traveler is referenced by expenses and cannot be removed")
    db.delete(traveler)
    db.commit()
