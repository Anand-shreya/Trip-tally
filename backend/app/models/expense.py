from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("uq_expense_trip_idempotency", "trip_id", "idempotency_key", unique=True),
    )

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category: Mapped[str] = mapped_column(String(50), index=True)
    paid_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("travelers.id"), index=True)
    expense_date: Mapped[date] = mapped_column(Date, index=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))

    trip: Mapped["Trip"] = relationship(back_populates="expenses")
    paid_by_traveler: Mapped["Traveler"] = relationship(
        back_populates="paid_expenses", foreign_keys=[paid_by]
    )
    splits: Mapped[list["ExpenseSplit"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseSplit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "expense_splits"

    expense_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("expenses.id", ondelete="CASCADE"), index=True
    )
    traveler_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("travelers.id"), index=True)
    share_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    expense: Mapped[Expense] = relationship(back_populates="splits")
    traveler: Mapped["Traveler"] = relationship(back_populates="expense_splits")


from app.models.traveler import Traveler  # noqa: E402, F401
from app.models.trip import Trip  # noqa: E402, F401

