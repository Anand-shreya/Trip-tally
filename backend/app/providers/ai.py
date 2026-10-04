from datetime import datetime, time, timedelta
from decimal import Decimal

from app.models import Place, Trip
from app.schemas.itinerary import ActivityPlan, ItineraryDayPlan, ItineraryPlan


def generate_itinerary(trip: Trip, places: list[Place]) -> ItineraryPlan:
    """Structured deterministic provider used when an OpenAI key is not configured."""
    days: list[ItineraryDayPlan] = []
    for index in range(trip.number_of_days):
        place = places[index % len(places)]
        current_date = trip.start_date + timedelta(days=index)
        morning = ActivityPlan(
            title=f"Explore {place.name}",
            description=f"Start with the essential sights and stories of {place.name} at an unhurried pace.",
            activity_type="SIGHTSEEING",
            start_time=time(9, 0),
            end_time=time(12, 0),
            location_name=place.name,
            latitude=place.latitude,
            longitude=place.longitude,
            estimated_cost=(place.estimated_tickets + place.estimated_activity) / max(1, trip.number_of_days),
        )
        evening = ActivityPlan(
            title="Local table",
            description="Choose a well-reviewed local restaurant and leave room for a slow evening walk.",
            activity_type="FOOD",
            start_time=time(18, 30),
            end_time=time(20, 30),
            location_name=place.name,
            latitude=place.latitude,
            longitude=place.longitude,
            estimated_cost=place.estimated_food / max(1, trip.number_of_days),
        )
        days.append(
            ItineraryDayPlan(
                day=index + 1,
                date=current_date,
                title=f"{place.name} — day {index + 1}",
                summary=f"A balanced day of discovery and downtime in {place.name}.",
                activities=[morning, evening],
            )
        )
    return ItineraryPlan(days=days)


def generate_summary_text(
    *, budget: Decimal | None, total_spent: Decimal, top_category: str | None, currency: str
) -> str:
    category_text = (
        f" {top_category.title()} was the largest spending category." if top_category else ""
    )
    if budget is None:
        return f"The trip recorded {total_spent:.2f} {currency} in shared spending.{category_text}"
    difference = budget - total_spent
    if difference >= 0:
        return (
            f"You stayed within the {budget:.2f} {currency} budget, with {difference:.2f} "
            f"{currency} remaining.{category_text}"
        )
    return (
        f"The trip finished {abs(difference):.2f} {currency} over the {budget:.2f} "
        f"{currency} budget.{category_text}"
    )

