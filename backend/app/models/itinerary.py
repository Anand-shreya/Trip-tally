from datetime import date, time
from decimal import Decimal

from sqlalchemy import Date, Float, ForeignKey, Integer, Numeric, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import UUIDPrimaryKeyMixin


class ItineraryDay(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "itinerary_days"

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    day_number: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)

    trip: Mapped["Trip"] = relationship(back_populates="itinerary_days")
    activities: Mapped[list["ItineraryActivity"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="ItineraryActivity.start_time"
    )


class ItineraryActivity(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "itinerary_activities"

    itinerary_day_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("itinerary_days.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    activity_type: Mapped[str] = mapped_column(String(50))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    location_name: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    day: Mapped[ItineraryDay] = relationship(back_populates="activities")


from app.models.trip import Trip  # noqa: E402, F401

