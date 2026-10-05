from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TripPlanningProfile(Base):
    __tablename__ = "trip_planning_profiles"

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("trips.id", ondelete="CASCADE"),
        primary_key=True,
    )
    departure_city: Mapped[str] = mapped_column(String(200), nullable=False)
    weather_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    budget_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weather_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    budget_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="planning_profile")


from app.models.trip import Trip  # noqa: E402, F401
