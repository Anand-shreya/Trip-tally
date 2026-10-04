from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models import Trip
from app.services.trip_service import get_trip


DbSession = Annotated[Session, Depends(get_db)]


def current_user_id() -> str:
    return get_settings().demo_user_id


CurrentUserId = Annotated[str, Depends(current_user_id)]


def owned_trip(
    db: DbSession,
    user_id: CurrentUserId,
    trip_id: Annotated[str, Path()],
) -> Trip:
    return get_trip(db, trip_id, user_id)


OwnedTrip = Annotated[Trip, Depends(owned_trip)]

