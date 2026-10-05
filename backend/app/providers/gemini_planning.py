import asyncio
import json
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.providers.gemini import GeminiProvider
from app.schemas.planning import (
    BudgetFacts,
    BudgetReport,
    EstimateRange,
    GeminiBudgetResult,
    GeminiPlacesResult,
    PlaceFacts,
    PlaceSuggestion,
)

BUDGET_INSTRUCTIONS = (
    "Estimate only the requested complete-trip budget for the complete travel party in the "
    "requested currency. Flights must be round-trip economy for the complete group. Return "
    "structured category numbers only; do not add places, itinerary, weather, or prose."
)
PLACE_INSTRUCTIONS = (
    "Return only relevant visitable places for the destination in relevance order. "
    "Return at most the requested count; do not add budget, weather, flights, or itinerary."
)
CATEGORY_NAMES = (
    "flights",
    "accommodation",
    "food",
    "local_transport",
    "tickets",
    "activities",
)


class PlanningProviderUnavailable(RuntimeError):
    pass


class InvalidPlanningResponse(RuntimeError):
    pass


class GeminiPlanningProvider:
    def __init__(self, *, provider: GeminiProvider) -> None:
        self._provider = provider
        self.model = provider.model

    async def estimate_budget(self, facts: BudgetFacts) -> BudgetReport:
        try:
            response = await asyncio.to_thread(
                self._provider.generate_structured,
                instructions=BUDGET_INSTRUCTIONS,
                input_messages=[
                    {
                        "role": "user",
                        "content": json.dumps(facts.model_dump(mode="json"), separators=(",", ":")),
                    }
                ],
                text_format=GeminiBudgetResult,
                max_output_tokens=900,
            )
            result = GeminiBudgetResult.model_validate(response)
            if result.currency != facts.currency:
                raise InvalidPlanningResponse("invalid provider response")
            ranges = [getattr(result.categories, name) for name in CATEGORY_NAMES]
            total = EstimateRange(
                minimum=sum((item.minimum for item in ranges), Decimal("0")),
                typical=sum((item.typical for item in ranges), Decimal("0")),
                maximum=sum((item.maximum for item in ranges), Decimal("0")),
            )
            return BudgetReport(
                currency=result.currency,
                traveler_count=facts.traveler_count,
                number_of_days=facts.number_of_days,
                categories=result.categories,
                total=total,
            )
        except InvalidPlanningResponse:
            raise
        except httpx.HTTPError:
            raise PlanningProviderUnavailable("planning provider unavailable") from None
        except Exception:
            raise InvalidPlanningResponse("invalid provider response") from None

    async def discover_places(self, facts: PlaceFacts) -> list[PlaceSuggestion]:
        try:
            response = await asyncio.to_thread(
                self._provider.generate_structured,
                instructions=PLACE_INSTRUCTIONS,
                input_messages=[
                    {
                        "role": "user",
                        "content": json.dumps(facts.model_dump(mode="json"), separators=(",", ":")),
                    }
                ],
                text_format=GeminiPlacesResult,
                max_output_tokens=3200,
            )
            result = GeminiPlacesResult.model_validate(response)
            deduplicated: list[PlaceSuggestion] = []
            seen_names: set[str] = set()
            for place in result.places:
                if place.recommended_days > facts.number_of_days:
                    raise InvalidPlanningResponse("invalid provider response")
                normalized = place.name.casefold()
                if normalized not in seen_names:
                    seen_names.add(normalized)
                    deduplicated.append(place)
            if not deduplicated:
                raise InvalidPlanningResponse("invalid provider response")
            return deduplicated
        except InvalidPlanningResponse:
            raise
        except httpx.HTTPError:
            raise PlanningProviderUnavailable("planning provider unavailable") from None
        except Exception:
            raise InvalidPlanningResponse("invalid provider response") from None

    def close(self) -> None:
        self._provider.close()


def build_gemini_planning_provider() -> GeminiPlanningProvider:
    settings = get_settings()
    if not settings.gemini_enabled or not settings.gemini_api_key or not settings.gemini_model:
        raise PlanningProviderUnavailable("planning provider unavailable")
    return GeminiPlanningProvider(
        provider=GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
    )
