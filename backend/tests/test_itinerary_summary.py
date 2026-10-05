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


class FakeStream:
    def __init__(self, *, parsed, events=None):
        self.parsed = parsed
        self.events = events if events is not None else [SimpleNamespace(type="response.completed")]

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_response(self):
        return SimpleNamespace(output_parsed=self.parsed)


class FakeResponses:
    def __init__(self, *, parsed=None, events=None, error=None):
        self.parsed = parsed
        self.events = events
        self.error = error
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeStream(parsed=self.parsed, events=self.events)


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


def test_chatgpt_stream_sets_store_false_and_returns_only_after_completion(db):
    from app.providers.ai import generate_itinerary, generate_local_itinerary
    from app.schemas.itinerary import ItineraryPlan

    trip = itinerary_trip(db)
    expected = generate_local_itinerary(trip, trip.places)
    client = SimpleNamespace(responses=FakeResponses(parsed=expected))
    result = generate_itinerary(trip, trip.places, client=client, model="gpt-test")

    assert result == expected
    call = client.responses.calls[0]
    assert call["model"] == "gpt-test"
    assert call["text_format"] is ItineraryPlan
    assert call["store"] is False
    assert "Sri Lanka" in call["input"][1]["content"]


def test_stream_requires_completed_event(db):
    from app.providers.ai import generate_itinerary, generate_local_itinerary

    trip = itinerary_trip(db)
    expected = generate_local_itinerary(trip, trip.places)
    client = SimpleNamespace(responses=FakeResponses(parsed=expected, events=[]))

    with pytest.raises(RuntimeError, match="before completion"):
        generate_itinerary(trip, trip.places, client=client, model="gpt-test")


def test_openai_summary_adapter_receives_verified_financial_facts():
    from app.providers.ai import SummaryNarrative, generate_summary_text

    client = SimpleNamespace(
        responses=FakeResponses(parsed=SummaryNarrative(summary="Verified figures, concise story."))
    )
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

    client = SimpleNamespace(
        responses=FakeResponses(parsed=SummaryNarrative(summary="No budget was set."))
    )
    result = generate_summary_text(
        budget=None,
        total_spent=Decimal("2500"),
        top_category=None,
        currency="INR",
        client=client,
    )

    assert result == "No budget was set."
    assert '"remaining": null' in client.responses.calls[0]["input"][1]["content"]


def test_openai_summary_failure_falls_back_to_local_prose():
    from app.providers.ai import generate_summary_text

    result = generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
        client=SimpleNamespace(responses=FakeResponses(error=RuntimeError("provider unavailable"))),
    )

    assert "within" in result.lower()
    assert "3550.00 INR remaining" in result


def test_stored_openai_key_is_not_used_until_explicitly_enabled(monkeypatch):
    import sys

    from app.providers import ai as ai_module

    class ForbiddenOpenAI:
        def __init__(self, **_kwargs):
            raise AssertionError("OpenAI client must remain disabled")

    monkeypatch.setattr(
        ai_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_enabled=False,
            openai_api_key="stored-but-disabled",
            openai_model="gpt-test",
        ),
    )
    monkeypatch.setattr(
        ai_module,
        "get_chatgpt_service",
        lambda: SimpleNamespace(
            inference_credentials=lambda: None,
            status=lambda: SimpleNamespace(signed_in=False),
        ),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=ForbiddenOpenAI))

    result = ai_module.generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
    )

    assert "3550.00 INR remaining" in result


def test_stored_openai_key_is_used_only_after_explicit_enable(monkeypatch):
    import sys

    from app.providers import ai as ai_module

    class EnabledOpenAI:
        def __init__(self, *, api_key):
            assert api_key == "enabled-test-key"
            self.responses = FakeResponses(
                parsed=ai_module.SummaryNarrative(summary="Explicitly enabled response.")
            )

    monkeypatch.setattr(
        ai_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_enabled=True,
            openai_api_key="enabled-test-key",
            openai_model="gpt-test",
        ),
    )
    monkeypatch.setattr(
        ai_module,
        "get_chatgpt_service",
        lambda: SimpleNamespace(
            inference_credentials=lambda: None,
            status=lambda: SimpleNamespace(signed_in=False),
        ),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=EnabledOpenAI))

    result = ai_module.generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
    )

    assert result == "Explicitly enabled response."


def test_connected_chatgpt_precedes_enabled_api_key(monkeypatch):
    import sys

    from app.providers import ai as ai_module

    constructed = []

    class OAuthOpenAI:
        def __init__(self, **kwargs):
            constructed.append(kwargs)
            self.responses = FakeResponses(
                parsed=ai_module.SummaryNarrative(summary="Generated with ChatGPT plan.")
            )

    monkeypatch.setattr(
        ai_module,
        "get_chatgpt_service",
        lambda: SimpleNamespace(inference_credentials=lambda: ("oauth-access-token", "gpt-plan")),
    )
    monkeypatch.setattr(
        ai_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_enabled=True,
            openai_api_key="paid-api-key",
            openai_model="gpt-api",
        ),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=OAuthOpenAI))

    result = ai_module.generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
    )

    assert result == "Generated with ChatGPT plan."
    assert constructed == [
        {
            "api_key": "oauth-access-token",
            "base_url": "https://api.openai.com/v1",
            "max_retries": 0,
        }
    ]


def test_chatgpt_plan_failure_never_falls_through_to_paid_api_key(monkeypatch):
    import sys

    from app.providers import ai as ai_module

    constructed_with = []

    class FailingOpenAI:
        def __init__(self, **kwargs):
            constructed_with.append(kwargs["api_key"])
            self.responses = FakeResponses(error=RuntimeError("plan unavailable"))

    monkeypatch.setattr(
        ai_module,
        "get_chatgpt_service",
        lambda: SimpleNamespace(inference_credentials=lambda: ("oauth-access-token", "gpt-plan")),
    )
    monkeypatch.setattr(
        ai_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_enabled=True,
            openai_api_key="paid-api-key",
            openai_model="gpt-api",
        ),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FailingOpenAI))

    result = ai_module.generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
    )

    assert "3550.00 INR remaining" in result
    assert constructed_with == ["oauth-access-token"]


def test_chatgpt_refresh_failure_uses_local_summary_without_paid_fallback(monkeypatch):
    import sys

    from app.providers import ai as ai_module

    class ForbiddenOpenAI:
        def __init__(self, **_kwargs):
            raise AssertionError("A failed ChatGPT refresh must not use the API key")

    def fail_refresh():
        raise RuntimeError("refresh token expired")

    monkeypatch.setattr(
        ai_module,
        "get_chatgpt_service",
        lambda: SimpleNamespace(inference_credentials=fail_refresh),
    )
    monkeypatch.setattr(
        ai_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_enabled=True,
            openai_api_key="paid-api-key",
            openai_model="gpt-api",
        ),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=ForbiddenOpenAI))

    result = ai_module.generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
    )

    assert "3550.00 INR remaining" in result


def test_connected_account_without_plan_scope_never_uses_paid_api_key(monkeypatch):
    import sys

    from app.providers import ai as ai_module

    class ForbiddenOpenAI:
        def __init__(self, **_kwargs):
            raise AssertionError("A connected ChatGPT account must not fall through to API billing")

    monkeypatch.setattr(
        ai_module,
        "get_chatgpt_service",
        lambda: SimpleNamespace(
            inference_credentials=lambda: None,
            status=lambda: SimpleNamespace(signed_in=True, selected_model=None),
        ),
    )
    monkeypatch.setattr(
        ai_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_enabled=True,
            openai_api_key="paid-api-key",
            openai_model="gpt-api",
        ),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=ForbiddenOpenAI))

    result = ai_module.generate_summary_text(
        budget=Decimal("80000"),
        total_spent=Decimal("76450"),
        top_category="ACCOMMODATION",
        currency="INR",
    )

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
