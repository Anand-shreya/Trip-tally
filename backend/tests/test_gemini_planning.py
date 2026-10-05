import json
from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest


class RecordingProvider:
    model = "gemini-3.5-flash-lite"

    def __init__(self, responses=None, error: Exception | None = None):
        self.responses = responses or {}
        self.error = error
        self.calls: list[SimpleNamespace] = []
        self.closed = False

    def generate_structured(
        self, *, instructions, input_messages, text_format, max_output_tokens=None
    ):
        self.calls.append(
            SimpleNamespace(
                instructions=instructions,
                input_messages=input_messages,
                text_format=text_format,
                max_output_tokens=max_output_tokens,
            )
        )
        if self.error is not None:
            raise self.error
        return text_format.model_validate(deepcopy(self.responses[text_format.__name__]))

    def close(self):
        self.closed = True


def valid_budget_payload(currency="INR"):
    return {
        "currency": currency,
        "categories": {
            "flights": {"minimum": "40000", "typical": "50000", "maximum": "65000"},
            "accommodation": {"minimum": "20000", "typical": "30000", "maximum": "45000"},
            "food": {"minimum": "8000", "typical": "12000", "maximum": "18000"},
            "local_transport": {"minimum": "4000", "typical": "7000", "maximum": "10000"},
            "tickets": {"minimum": "3000", "typical": "5000", "maximum": "8000"},
            "activities": {"minimum": "5000", "typical": "9000", "maximum": "14000"},
        },
    }


def place_payload(name="Red Fort"):
    return {
        "name": name,
        "description": "Mughal citadel and museum complex.",
        "latitude": 28.6562,
        "longitude": 77.2410,
        "recommended_days": "0.5",
        "best_for": ["History", "Architecture"],
        "relevance_score": "9.4",
    }


@pytest.mark.asyncio
async def test_budget_request_contains_only_budget_facts_and_computes_totals():
    from app.providers.gemini_planning import GeminiPlanningProvider
    from app.schemas.planning import BudgetFacts

    provider = RecordingProvider({"GeminiBudgetResult": valid_budget_payload()})
    planning = GeminiPlanningProvider(provider=provider)
    facts = BudgetFacts(
        departure_city="Delhi",
        destination="Kyoto",
        start_date=date(2027, 4, 4),
        number_of_days=5,
        traveler_count=2,
        travel_style="COMFORTABLE",
        currency="INR",
    )

    result = await planning.estimate_budget(facts)

    assert len(provider.calls) == 1
    call = provider.calls[0]
    budget_payload = json.loads(call.input_messages[0]["content"])
    assert set(budget_payload) == {
        "departure_city",
        "destination",
        "start_date",
        "number_of_days",
        "traveler_count",
        "travel_style",
        "currency",
    }
    assert call.max_output_tokens == 900
    assert "round-trip economy" in call.instructions.lower()
    assert "relevant visitable places" not in call.instructions.lower()
    assert result.total.minimum == Decimal("80000")
    assert result.total.typical == Decimal("113000")
    assert result.total.maximum == Decimal("160000")
    assert result.traveler_count == 2
    assert result.number_of_days == 5


@pytest.mark.asyncio
async def test_place_request_contains_only_place_facts_and_deduplicates_names():
    from app.providers.gemini_planning import GeminiPlanningProvider
    from app.schemas.planning import PlaceFacts

    provider = RecordingProvider(
        {
            "GeminiPlacesResult": {
                "places": [
                    place_payload("Red Fort"),
                    place_payload("red fort"),
                    {**place_payload("India Gate"), "relevance_score": "8.8"},
                ]
            }
        }
    )
    planning = GeminiPlanningProvider(provider=provider)
    facts = PlaceFacts(
        destination="Delhi",
        number_of_days=3,
        travel_style="COMFORTABLE",
    )

    result = await planning.discover_places(facts)

    assert len(provider.calls) == 1
    call = provider.calls[0]
    places_payload = json.loads(call.input_messages[0]["content"])
    assert set(places_payload) == {
        "destination",
        "number_of_days",
        "travel_style",
        "maximum_results",
    }
    assert places_payload["maximum_results"] == 20
    assert call.max_output_tokens == 3200
    assert [place.name for place in result] == ["Red Fort", "India Gate"]


@pytest.mark.asyncio
async def test_budget_rejects_wrong_currency():
    from app.providers.gemini_planning import GeminiPlanningProvider, InvalidPlanningResponse
    from app.schemas.planning import BudgetFacts

    provider = RecordingProvider({"GeminiBudgetResult": valid_budget_payload("USD")})
    planning = GeminiPlanningProvider(provider=provider)

    with pytest.raises(InvalidPlanningResponse, match="invalid provider response"):
        await planning.estimate_budget(
            BudgetFacts(
                departure_city="Delhi",
                destination="Kyoto",
                start_date=date(2027, 4, 4),
                number_of_days=5,
                traveler_count=2,
                travel_style="COMFORTABLE",
                currency="INR",
            )
        )


@pytest.mark.asyncio
async def test_budget_rejects_reversed_range():
    from app.providers.gemini_planning import GeminiPlanningProvider, InvalidPlanningResponse
    from app.schemas.planning import BudgetFacts

    payload = valid_budget_payload()
    payload["categories"]["food"] = {
        "minimum": "15000",
        "typical": "12000",
        "maximum": "18000",
    }
    planning = GeminiPlanningProvider(provider=RecordingProvider({"GeminiBudgetResult": payload}))

    with pytest.raises(InvalidPlanningResponse, match="invalid provider response"):
        await planning.estimate_budget(
            BudgetFacts(
                departure_city="Delhi",
                destination="Kyoto",
                start_date=date(2027, 4, 4),
                number_of_days=5,
                traveler_count=2,
                travel_style="COMFORTABLE",
                currency="INR",
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda places: places.extend([place_payload(f"Place {index}") for index in range(20)]),
        lambda places: places[0].update({"recommended_days": "4"}),
        lambda places: places[0].update({"latitude": 100}),
        lambda places: places[0].update({"description": "x" * 241}),
        lambda places: places[0].update({"best_for": ["a", "b", "c", "d", "e"]}),
    ],
    ids=["over-20", "over-duration", "coordinates", "description", "tags"],
)
async def test_place_response_rejects_invalid_results(mutate):
    from app.providers.gemini_planning import GeminiPlanningProvider, InvalidPlanningResponse
    from app.schemas.planning import PlaceFacts

    places = [place_payload()]
    mutate(places)
    planning = GeminiPlanningProvider(
        provider=RecordingProvider({"GeminiPlacesResult": {"places": places}})
    )

    with pytest.raises(InvalidPlanningResponse, match="invalid provider response"):
        await planning.discover_places(
            PlaceFacts(
                destination="Delhi",
                number_of_days=3,
                travel_style="COMFORTABLE",
            )
        )


@pytest.mark.asyncio
async def test_network_failure_is_wrapped_without_upstream_details():
    from app.providers.gemini_planning import GeminiPlanningProvider, PlanningProviderUnavailable
    from app.schemas.planning import BudgetFacts

    request = httpx.Request("POST", "https://example.test?key=secret-key")
    planning = GeminiPlanningProvider(
        provider=RecordingProvider(
            error=httpx.ConnectError("secret upstream detail", request=request)
        )
    )

    with pytest.raises(PlanningProviderUnavailable) as captured:
        await planning.estimate_budget(
            BudgetFacts(
                departure_city="Delhi",
                destination="Kyoto",
                start_date=date(2027, 4, 4),
                number_of_days=5,
                traveler_count=2,
                travel_style="COMFORTABLE",
                currency="INR",
            )
        )

    assert str(captured.value) == "planning provider unavailable"
    assert "secret" not in str(captured.value)


def test_provider_factory_fails_safely_when_gemini_is_disabled(monkeypatch):
    from app.providers import gemini_planning

    monkeypatch.setattr(
        gemini_planning,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_enabled=False,
            gemini_api_key="secret-key",
            gemini_model="gemini-3.5-flash-lite",
        ),
    )

    with pytest.raises(gemini_planning.PlanningProviderUnavailable) as captured:
        gemini_planning.build_gemini_planning_provider()

    assert str(captured.value) == "planning provider unavailable"
    assert "secret-key" not in str(captured.value)
