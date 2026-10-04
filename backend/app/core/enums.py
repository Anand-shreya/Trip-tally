from enum import StrEnum


class TravelStyle(StrEnum):
    BUDGET = "BUDGET"
    COMFORTABLE = "COMFORTABLE"
    PREMIUM = "PREMIUM"


class TripStatus(StrEnum):
    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class ExpenseCategory(StrEnum):
    FOOD = "FOOD"
    ACCOMMODATION = "ACCOMMODATION"
    TRANSPORT = "TRANSPORT"
    ACTIVITIES = "ACTIVITIES"
    TICKETS = "TICKETS"
    SHOPPING = "SHOPPING"
    OTHER = "OTHER"


class SplitType(StrEnum):
    EQUAL = "EQUAL"
    CUSTOM = "CUSTOM"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"
    DEAD = "DEAD"


class JobType(StrEnum):
    GENERATE_ITINERARY = "GENERATE_ITINERARY"
    GENERATE_SUMMARY = "GENERATE_SUMMARY"

