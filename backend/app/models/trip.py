from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class Trip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trips"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    number_of_days: Mapped[int] = mapped_column(Integer)
    base_currency: Mapped[str] = mapped_column(String(3), default="INR")
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    travel_style: Mapped[str] = mapped_column(String(20), default="COMFORTABLE")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    weather_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    weather_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weather_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_cost_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_cost_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    user: Mapped["User"] = relationship(back_populates="trips")
    travelers: Mapped[list["Traveler"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    places: Mapped[list["Place"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    itinerary_days: Mapped[list["ItineraryDay"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", order_by="ItineraryDay.day_number"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    archive_record: Mapped["TripArchive | None"] = relationship(
        back_populates="trip", cascade="all, delete-orphan", single_parent=True, uselist=False
    )

    @property
    def is_archived(self) -> bool:
        return self.archive_record is not None

    @property
    def archived_at(self) -> datetime | None:
        return self.archive_record.archived_at if self.archive_record else None


class TripArchive(Base):
    __tablename__ = "trip_archives"

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    trip: Mapped[Trip] = relationship(back_populates="archive_record")


from app.models.expense import Expense  # noqa: E402, F401
from app.models.itinerary import ItineraryDay  # noqa: E402, F401
from app.models.job import Job  # noqa: E402, F401
from app.models.place import Place  # noqa: E402, F401
from app.models.traveler import Traveler  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
