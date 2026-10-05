import asyncio
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError


def make_user(db, email="owner@tripwise.local"):
    from app.models import User

    user = User(name="Owner", email=email)
    db.add(user)
    db.commit()
    return user


def create_test_trip(db, *, name="Japan spring", destination="Kyoto", with_profile=True):
    from app.models import Trip
    from app.schemas.trip import TripCreate
    from app.services.trip_service import create_trip

    user = make_user(db, f"{name.lower().replace(' ', '-')}@example.test")
    if with_profile:
        return create_trip(
            db,
            user.id,
            TripCreate(
                name=name,
                departure_city="Delhi",
                destination=destination,
                start_date=date(2027, 4, 4),
                number_of_days=5,
                budget=Decimal("180000"),
                currency="INR",
                travel_style="COMFORTABLE",
            ),
        )
    trip = Trip(
        user=user,
        name=name,
        destination=destination,
        start_date=date(2027, 4, 4),
        end_date=date(2027, 4, 8),
        number_of_days=5,
        base_currency="INR",
        budget=Decimal("180000"),
        travel_style="COMFORTABLE",
        status="PLANNING",
    )
    db.add(trip)
    db.commit()
    return trip


def weather_report():
    from app.schemas.planning import CurrentWeather, DailyWeather, ResolvedLocation, WeatherReport

    return WeatherReport(
        location=ResolvedLocation(
            name="Kyoto",
            country_code="JP",
            latitude=35.0116,
            longitude=135.7681,
            timezone_offset_seconds=32400,
        ),
        current=CurrentWeather(
            observed_at=datetime(2026, 10, 5, 12, tzinfo=UTC),
            condition="Clear",
            description="clear sky",
            temperature_c=Decimal("24.0"),
            feels_like_c=Decimal("24.5"),
            minimum_c=Decimal("18.0"),
            maximum_c=Decimal("26.0"),
            humidity_percent=55,
            pressure_hpa=1014,
            visibility_m=10000,
            cloud_percent=5,
            wind_speed_kph=Decimal("8.0"),
            wind_direction_degrees=120,
            sunrise_at=datetime(2026, 10, 5, 21, tzinfo=UTC),
            sunset_at=datetime(2026, 10, 6, 9, tzinfo=UTC),
        ),
        daily=[
            DailyWeather(
                requested_date=date(2027, 4, 4),
                source_date=date(2026, 4, 4),
                source="historical",
                minimum_c=Decimal("12.0"),
                maximum_c=Decimal("21.0"),
                representative_c=Decimal("17.0"),
                condition="Partly cloudy",
                precipitation_mm=Decimal("1.2"),
                maximum_wind_kph=Decimal("11.0"),
            )
        ],
        source="openweather+open-meteo",
        summary="Current conditions in Kyoto: clear sky, 24.0°C, 55% humidity, wind 8.0 km/h.",
    )


def budget_report():
    from app.schemas.planning import BudgetCategories, BudgetReport, EstimateRange

    categories = BudgetCategories(
        flights=EstimateRange(minimum=50000, typical=60000, maximum=70000),
        accommodation=EstimateRange(minimum=20000, typical=30000, maximum=40000),
        food=EstimateRange(minimum=8000, typical=12000, maximum=16000),
        local_transport=EstimateRange(minimum=5000, typical=8000, maximum=12000),
        tickets=EstimateRange(minimum=3000, typical=5000, maximum=8000),
        activities=EstimateRange(minimum=5000, typical=10000, maximum=15000),
    )
    return BudgetReport(
        currency="INR",
        traveler_count=1,
        number_of_days=5,
        categories=categories,
        total=EstimateRange(minimum=91000, typical=125000, maximum=161000),
    )


def place_suggestions(*names):
    from app.schemas.planning import PlaceSuggestion

    selected_names = names or ("Fushimi Inari", "Kiyomizu-dera")
    return [
        PlaceSuggestion(
            name=name,
            description=f"Visit {name} for a focused local experience.",
            latitude=35.0 + index / 100,
            longitude=135.7 + index / 100,
            recommended_days=Decimal("0.5"),
            best_for=["Culture", "History"],
            relevance_score=Decimal("9.4") - index,
        )
        for index, name in enumerate(selected_names)
    ]


async def successful_weather(*_args):
    return weather_report()


class FakePlanningProvider:
    model = "gemini-3.5-flash-lite"

    def __init__(
        self,
        *,
        budget=None,
        places=None,
        budget_error=None,
        places_error=None,
        started=None,
        release=None,
    ):
        self.budget_result = budget or budget_report()
        self.place_result = places or place_suggestions()
        self.budget_error = budget_error
        self.places_error = places_error
        self.started = started
        self.release = release
        self.budget_calls = 0
        self.place_calls = 0
        self.budget_facts = None
        self.place_facts = None
        self.closed = False

    async def estimate_budget(self, facts):
        self.budget_calls += 1
        self.budget_facts = facts
        if self.started is not None:
            self.started.add("budget")
        if self.release is not None:
            await self.release.wait()
        if self.budget_error is not None:
            raise self.budget_error
        return self.budget_result

    async def discover_places(self, facts):
        self.place_calls += 1
        self.place_facts = facts
        if self.started is not None:
            self.started.add("places")
        if self.release is not None:
            await self.release.wait()
        if self.places_error is not None:
            raise self.places_error
        return self.place_result

    def close(self):
        self.closed = True


def test_create_trip_derives_dates_currency_and_profile(db):
    trip = create_test_trip(db)

    assert trip.end_date == date(2027, 4, 8)
    assert trip.base_currency == "INR"
    assert trip.status == "PLANNING"
    assert trip.departure_city == "Delhi"
    assert trip.planning_profile.weather_report is None


def test_legacy_trip_without_profile_reads_null_departure_city(db):
    trip = create_test_trip(db, with_profile=False)

    assert trip.departure_city is None


def test_trip_create_requires_nonblank_departure_city():
    from app.schemas.trip import TripCreate

    with pytest.raises(PydanticValidationError):
        TripCreate(
            name="Trip",
            departure_city="   ",
            destination="Goa",
            start_date=date(2027, 1, 1),
            number_of_days=2,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("number_of_days", 0), ("budget", Decimal("-0.01")), ("currency", "RUPEE")],
)
def test_trip_request_rejects_invalid_values(field, value):
    from app.schemas.trip import TripCreate

    data = {
        "name": "Trip",
        "departure_city": "Delhi",
        "destination": "Goa",
        "start_date": date(2026, 1, 1),
        "number_of_days": 2,
        "budget": Decimal("1000"),
        "currency": "INR",
        "travel_style": "BUDGET",
    }
    data[field] = value
    with pytest.raises(PydanticValidationError):
        TripCreate(**data)


def test_trip_lookup_hides_another_users_trip(db):
    from app.core.exceptions import NotFoundError
    from app.services.trip_service import get_trip

    trip = create_test_trip(db, name="Private")
    stranger = make_user(db, "stranger@tripwise.local")

    with pytest.raises(NotFoundError):
        get_trip(db, trip.id, stranger.id)


@pytest.mark.asyncio
async def test_analysis_starts_all_provider_operations_before_waiting_and_persists_once(db):
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip

    trip = create_test_trip(db)
    started: set[str] = set()
    release = asyncio.Event()
    provider = FakePlanningProvider(started=started, release=release)

    async def gated_weather(*_args):
        started.add("weather")
        await release.wait()
        return weather_report()

    analysis_task = asyncio.create_task(
        analyze_trip(
            db,
            trip,
            AnalyzeTripRequest(),
            weather_fetcher=gated_weather,
            planning_provider=provider,
        )
    )
    for _ in range(20):
        if started == {"weather", "budget", "places"}:
            break
        await asyncio.sleep(0)

    assert started == {"weather", "budget", "places"}
    release.set()
    result = await analysis_task

    assert result.status == "READY"
    assert result.budget.total.typical == Decimal("125000")
    assert result.weather.current.condition == "Clear"
    assert len(result.places) == 2
    assert provider.budget_calls == 1
    assert provider.place_calls == 1
    assert provider.budget_facts.traveler_count == 1
    assert provider.closed is False
    assert trip.planning_profile.weather_source == "openweather+open-meteo"
    assert trip.planning_profile.budget_model == "gemini-3.5-flash-lite"
    assert trip.weather_score is None
    assert trip.weather_rating is None
    assert trip.estimated_cost == Decimal("125000")
    assert all(place.relevance_score <= 10 for place in result.places)
    assert all(not hasattr(place, "weather_score") for place in result.places)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failed_stage", "expected_code"),
    [
        ("weather", "weather_unavailable"),
        ("budget", "budget_unavailable"),
        ("places", "places_unavailable"),
        ("invalid", "invalid_provider_response"),
    ],
)
async def test_failed_refresh_preserves_last_successful_report_and_selection(
    db, failed_stage, expected_code
):
    from app.core.exceptions import ProviderError
    from app.providers.gemini_planning import (
        InvalidPlanningResponse,
        PlanningProviderUnavailable,
    )
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip, list_places, select_places

    trip = create_test_trip(db)
    await analyze_trip(
        db,
        trip,
        AnalyzeTripRequest(),
        weather_fetcher=successful_weather,
        planning_provider=FakePlanningProvider(),
    )
    first_places = list_places(db, trip)
    select_places(db, trip, [first_places[0].id])
    profile_before = (
        deepcopy(trip.planning_profile.weather_report),
        deepcopy(trip.planning_profile.budget_report),
        trip.planning_profile.analyzed_at,
    )
    places_before = [(place.id, place.name, place.selected) for place in list_places(db, trip)]
    trip_before = (trip.weather_summary, trip.estimated_cost, trip.status)

    async def failing_weather(*_args):
        raise RuntimeError("upstream URL contains secret-key")

    unavailable = PlanningProviderUnavailable("private upstream detail")
    provider = FakePlanningProvider(
        budget_error=(
            InvalidPlanningResponse("private invalid JSON")
            if failed_stage == "invalid"
            else unavailable
            if failed_stage == "budget"
            else None
        ),
        places_error=unavailable if failed_stage == "places" else None,
    )

    with pytest.raises(ProviderError) as captured:
        await analyze_trip(
            db,
            trip,
            AnalyzeTripRequest(),
            weather_fetcher=failing_weather if failed_stage == "weather" else successful_weather,
            planning_provider=provider,
        )

    assert captured.value.detail == {"code": expected_code}
    assert "private" not in str(captured.value.detail)
    assert profile_before == (
        trip.planning_profile.weather_report,
        trip.planning_profile.budget_report,
        trip.planning_profile.analyzed_at,
    )
    assert places_before == [
        (place.id, place.name, place.selected) for place in list_places(db, trip)
    ]
    assert trip_before == (trip.weather_summary, trip.estimated_cost, trip.status)


@pytest.mark.asyncio
async def test_successful_refresh_preserves_case_insensitive_selection(db):
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip, list_places, select_places

    trip = create_test_trip(db)
    await analyze_trip(
        db,
        trip,
        AnalyzeTripRequest(),
        weather_fetcher=successful_weather,
        planning_provider=FakePlanningProvider(
            places=place_suggestions("Red Fort", "Lotus Temple")
        ),
    )
    first = list_places(db, trip)
    red_fort = next(place for place in first if place.name == "Red Fort")
    select_places(db, trip, [red_fort.id])

    await analyze_trip(
        db,
        trip,
        AnalyzeTripRequest(),
        weather_fetcher=successful_weather,
        planning_provider=FakePlanningProvider(places=place_suggestions("red fort", "India Gate")),
    )

    refreshed = list_places(db, trip)
    assert next(place for place in refreshed if place.name == "red fort").selected is True
    assert next(place for place in refreshed if place.name == "India Gate").selected is False


@pytest.mark.asyncio
async def test_legacy_trip_requires_departure_city_before_provider_calls(db):
    from app.core.exceptions import ValidationError
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip

    trip = create_test_trip(db, with_profile=False)
    provider = FakePlanningProvider()

    with pytest.raises(ValidationError, match="Departure city is required"):
        await analyze_trip(
            db,
            trip,
            AnalyzeTripRequest(),
            weather_fetcher=successful_weather,
            planning_provider=provider,
        )

    assert provider.budget_calls == 0
    assert provider.place_calls == 0


@pytest.mark.asyncio
async def test_analysis_read_uses_only_persisted_data(db):
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip, get_analysis

    trip = create_test_trip(db)
    provider = FakePlanningProvider()
    created = await analyze_trip(
        db,
        trip,
        AnalyzeTripRequest(),
        weather_fetcher=successful_weather,
        planning_provider=provider,
    )

    read = get_analysis(db, trip)

    assert read == created
    assert provider.budget_calls == 1
    assert provider.place_calls == 1


@pytest.mark.asyncio
async def test_analysis_read_serializes_persisted_timestamp_as_utc(db):
    from app.models import Trip
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip, get_analysis

    trip = create_test_trip(db)
    trip_id = trip.id
    created = await analyze_trip(
        db,
        trip,
        AnalyzeTripRequest(),
        weather_fetcher=successful_weather,
        planning_provider=FakePlanningProvider(),
    )
    created_timestamp = created.model_dump(mode="json")["analyzed_at"]

    db.expunge_all()
    reloaded_trip = db.get(Trip, trip_id)
    read_timestamp = get_analysis(db, reloaded_trip).model_dump(mode="json")["analyzed_at"]

    assert read_timestamp == created_timestamp
    assert read_timestamp.endswith("Z")


@pytest.mark.asyncio
async def test_select_places_rejects_place_from_another_trip(db):
    from app.core.exceptions import ValidationError
    from app.schemas.planning import AnalyzeTripRequest
    from app.services.planning_service import analyze_trip, list_places, select_places

    trip_a = create_test_trip(db, name="Trip A")
    trip_b = create_test_trip(db, name="Trip B")
    await analyze_trip(
        db,
        trip_b,
        AnalyzeTripRequest(),
        weather_fetcher=successful_weather,
        planning_provider=FakePlanningProvider(),
    )
    foreign_place = list_places(db, trip_b)[0]

    with pytest.raises(ValidationError, match="do not belong"):
        select_places(db, trip_a, [foreign_place.id])


def test_traveler_name_is_trimmed_and_cannot_be_empty(db):
    from app.schemas.trip import TravelerCreate

    assert TravelerCreate(name="  Shreya  ").name == "Shreya"
    with pytest.raises(PydanticValidationError):
        TravelerCreate(name="   ")
