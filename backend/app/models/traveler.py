from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Traveler(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "travelers"
    __table_args__ = (UniqueConstraint("trip_id", "name", name="uq_traveler_trip_name"),)

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    trip: Mapped["Trip"] = relationship(back_populates="travelers")
    paid_expenses: Mapped[list["Expense"]] = relationship(
        back_populates="paid_by_traveler", foreign_keys="Expense.paid_by"
    )
    expense_splits: Mapped[list["ExpenseSplit"]] = relationship(back_populates="traveler")


from app.models.expense import Expense, ExpenseSplit  # noqa: E402, F401
from app.models.trip import Trip  # noqa: E402, F401

