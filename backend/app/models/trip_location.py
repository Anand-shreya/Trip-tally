from sqlalchemy import Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TripLocation(Base):
    __tablename__ = "trip_locations"

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("trips.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_type: Mapped[str] = mapped_column(String(20), nullable=False)

    trip: Mapped["Trip"] = relationship(back_populates="locations")


from app.models.trip import Trip  # noqa: E402, F401
