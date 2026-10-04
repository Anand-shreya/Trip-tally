from decimal import Decimal

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Place(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "places"

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    recommended_days: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    estimated_food: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estimated_transport: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estimated_tickets: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estimated_activity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estimated_stay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    weather_score: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    overall_score: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    best_for: Mapped[list[str]] = mapped_column(JSON, default=list)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    trip: Mapped["Trip"] = relationship(back_populates="places")

    @property
    def estimated_cost(self) -> Decimal:
        return sum(
            (
                self.estimated_food,
                self.estimated_transport,
                self.estimated_tickets,
                self.estimated_activity,
                self.estimated_stay,
            ),
            Decimal("0"),
        )


from app.models.trip import Trip  # noqa: E402, F401
