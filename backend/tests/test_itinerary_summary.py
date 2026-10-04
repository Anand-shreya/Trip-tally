from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest


def itinerary_trip(db, *, selected=True):
    from app.models import Place, Traveler, Trip, User

    user = User(name="Owner", email="itinerary@tripwise.local")
    trip = Trip(
        user=user,
        name="Sri Lanka loop",
        destination="Sri Lanka",
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 7),
        number_of_days=3,
        base_currency="INR",
        budget=Decimal("30000"),
        travel_style="COMFORTABLE",
        status="READY",
        weather_score=Decimal("7.4"),
        weather_rating="GOOD",
        weather_summary="Pleasant with passing rain.",
    )
    trip.travelers = [Traveler(name="Shreya"), Traveler(name="Rahul")]
    trip.places = [
        Place(
            name="Kandy",
            description="Culture and lake walks",
            latitude=7.2906,
            longitude=80.6337,
            recommended_days=Decimal("2"),
            estimated_food=1000,
            estimated_transport=1000,
            estimated_tickets=500,
            estimated_activity=1500,
            estimated_stay=3000,
            weather_score=Decimal("7.4"),
            overall_score=Decimal("8.2"),
            best_for=["Culture"],
            selected=selected,
        )
    ]
    db.add(trip)
    db.commit()
    return trip


def test_itinerary_requires_a_selected_place(db):
    from app.core.exceptions import ValidationError
    from app.services.itinerary_service import enqueue_itinerary

    trip = itinerary_trip(db, selected=False)
    with pytest.raises(ValidationError, match="Select at least one"):
        enqueue_itinerary(db, trip, dispatch=False)


def test_itinerary_job_generates_exact_trip_days_and_valid_times(db):
    from app.services.itinerary_service import enqueue_itinerary, get_itinerary, run_itinerary_job

    trip = itinerary_trip(db)
    job = enqueue_itinerary(db, trip, dispatch=False)
    completed = run_itinerary_job(job.id, db=db)
    days = get_itinerary(db, trip)

    assert completed.status == "SUCCESS"
    assert [day.day_number for day in days] == [1, 2, 3]
    assert [day.date for day in days] == [date(2026, 9, 5), date(2026, 9, 6), date(2026, 9, 7)]
    assert all(
        activity.start_time < activity.end_time for day in days for activity in day.activities
    )


def test_invalid_replacement_keeps_existing_itinerary(db):
    from app.core.exceptions import ValidationError
    from app.schemas.itinerary import ItineraryPlan
    from app.services.itinerary_service import (
        enqueue_itinerary,
        get_itinerary,
        replace_itinerary,
        run_itinerary_job,
    )

    trip = itinerary_trip(db)
    job = enqueue_itinerary(db, trip, dispatch=False)
    run_itinerary_job(job.id, db=db)
    original_titles = [day.title for day in get_itinerary(db, trip)]

    with pytest.raises(ValidationError, match="exactly 3 days"):
        replace_itinerary(db, trip, ItineraryPlan(days=[]))

    assert [day.title for day in get_itinerary(db, trip)] == original_titles


def test_failed_job_retries_then_becomes_dead(db):
    from app.services.itinerary_service import enqueue_itinerary, run_itinerary_job

    trip = itinerary_trip(db)
    job = enqueue_itinerary(db, trip, dispatch=False)

    def broken_generator(_trip, _places):
        raise RuntimeError("provider unavailable")

    assert run_itinerary_job(job.id, db=db, generator=broken_generator).status == "RETRY"
    assert run_itinerary_job(job.id, db=db, generator=broken_generator).status == "RETRY"
    final = run_itinerary_job(job.id, db=db, generator=broken_generator)
    assert final.status == "DEAD"
    assert final.attempt == 3
    assert "provider unavailable" in final.error


def test_summary_uses_backend_totals_categories_and_fallback_prose(db):
    from app.schemas.expense import ExpenseCreate
    from app.services.expense_service import create_expense
    from app.services.summary_service import build_summary

    trip = itinerary_trip(db)
    payload = ExpenseCreate(
        description="Dinner",
        amount=Decimal("1200"),
        currency="INR",
        category="FOOD",
        paid_by=trip.travelers[0].id,
        expense_date=date(2026, 9, 5),
        included_travelers=[traveler.id for traveler in trip.travelers],
        split_type="EQUAL",
    )
    create_expense(db, trip, payload, "summary-expense")

    summary = build_summary(db, trip)

    assert summary.total_spent == Decimal("1200.00")
    assert summary.remaining == Decimal("28800.00")
    assert summary.categories == {"FOOD": Decimal("1200.00")}
    assert summary.average_per_day == Decimal("400.00")
    assert "within" in summary.ai_summary.lower()
    assert len(summary.traveler_balances) == 2


def test_openai_itinerary_adapter_uses_responses_structured_output(db):
    from app.providers.ai import generate_itinerary, generate_local_itinerary
    from app.schemas.itinerary import ItineraryPlan

    trip = itinerary_trip(db)
    expected = generate_local_itinerary(trip, trip.places)

    class Responses:
        def __init__(self):
            self.calls = []

        def parse(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(output_parsed=expected)

    client = SimpleNamespace(responses=Responses())
    result = generate_itinerary(trip, trip.places, client=client, model="gpt-test")

    assert result == expected
    call = client.responses.calls[0]
    assert call["model"] == "gpt-test"
    assert call["text_format"] is ItineraryPlan
    assert "Sri Lanka" in call["input"][1]["content"]


def test_openai_summary_adapter_receives_verified_financial_facts():
    from app.providers.ai import SummaryNarrative, generate_summary_text

    class Responses:
        def __init__(self):
            self.calls = []

        def parse(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=SummaryNarrative(summary="Verified figures, concise story.")
            )

    client = SimpleNamespace(responses=Responses())
    result = generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
        client=client,
        model="gpt-test",
    )

    assert result == "Verified figures, concise story."
    call = client.responses.calls[0]
    assert call["text_format"] is SummaryNarrative
    assert "76450" in call["input"][1]["content"]


def test_openai_summary_adapter_supports_an_unbudgeted_trip():
    from app.providers.ai import SummaryNarrative, generate_summary_text

    class Responses:
        def parse(self, **kwargs):
            assert '"remaining": null' in kwargs["input"][1]["content"]
            return SimpleNamespace(output_parsed=SummaryNarrative(summary="No budget was set."))

    client = SimpleNamespace(responses=Responses())
    result = generate_summary_text(
        budget=None,
        total_spent=Decimal("2500"),
        top_category=None,
        currency="INR",
        client=client,
    )

    assert result == "No budget was set."


def test_openai_summary_failure_falls_back_to_local_prose():
    from app.providers.ai import generate_summary_text

    class Responses:
        def parse(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    result = generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
        client=SimpleNamespace(responses=Responses()),
    )

    assert "within" in result.lower()
    assert "3550.00 INR remaining" in result


def test_rq_handler_raises_retryable_job_failures(monkeypatch):
    from app.workers.jobs import itinerary_job

    monkeypatch.setattr(
        itinerary_job,
        "run_itinerary_job",
        lambda _job_id: SimpleNamespace(status="RETRY", error="provider unavailable"),
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        itinerary_job.perform("job-1")


def test_redis_dispatch_configures_two_retries(monkeypatch):
    import sys

    from app.workers import queue as queue_module

    captured = {}

    class FakeRedis:
        @classmethod
        def from_url(cls, url):
            return url

    class FakeRetry:
        def __init__(self, *, max, interval):
            self.max = max
            self.interval = interval

    class FakeQueue:
        def __init__(self, name, *, connection):
            captured["queue"] = (name, connection)

        def enqueue(self, *args, **kwargs):
            captured["enqueue"] = (args, kwargs)

    monkeypatch.setattr(
        queue_module,
        "get_settings",
        lambda: SimpleNamespace(queue_mode="redis", redis_url="redis://queue/0"),
    )
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=FakeRedis))
    monkeypatch.setitem(sys.modules, "rq", SimpleNamespace(Queue=FakeQueue, Retry=FakeRetry))

    queue_module.dispatch_itinerary("job-1")

    retry = captured["enqueue"][1]["retry"]
    assert retry.max == 2
    assert retry.interval == [5, 15]
