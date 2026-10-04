from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import ExpenseCategory, SplitType


class CustomSplit(BaseModel):
    traveler_id: str
    amount: Decimal


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    category: ExpenseCategory
    paid_by: str
    expense_date: date
    included_travelers: list[str] = Field(min_length=1)
    split_type: SplitType = SplitType.EQUAL
    splits: list[CustomSplit] = Field(default_factory=list)
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = None

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Description cannot be empty")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ExpenseSplitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    traveler_id: str
    share_amount: Decimal


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    description: str
    amount: Decimal
    currency: str
    exchange_rate: Decimal
    base_amount: Decimal
    category: ExpenseCategory
    paid_by: str
    expense_date: date
    location: str | None
    notes: str | None
    created_at: datetime
    splits: list[ExpenseSplitRead]


class TravelerBalance(BaseModel):
    traveler_id: str
    traveler: str
    paid: Decimal
    owed: Decimal
    net: Decimal


class Settlement(BaseModel):
    from_traveler_id: str
    from_traveler: str
    to_traveler_id: str
    to_traveler: str
    amount: Decimal


class BalancesResponse(BaseModel):
    balances: list[TravelerBalance]


class SettlementsResponse(BaseModel):
    settlements: list[Settlement]

