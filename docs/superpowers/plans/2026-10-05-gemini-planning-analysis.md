# Gemini Planning Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace TripWise's deterministic planning analysis with persisted API weather, two narrowly scoped Gemini requests for budget and places, and a complete Plan page with keyless Google Maps links.

**Architecture:** Add a one-to-one planning profile without altering existing trip rows, fetch weather from OpenWeather/Open-Meteo, and run separate budget and place Gemini operations concurrently behind fakeable provider interfaces. Validate all results before one database transaction replaces the saved analysis, then render only persisted data on normal page loads.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, httpx, SQLite/PostgreSQL, React 19, TypeScript, TanStack Query, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-05-gemini-planning-analysis-design.md`

## Global Constraints

- Change files only inside `/Users/shreyaanand/Desktop/Go-pract/Projects/TripWise`.
- Do not use Slack, Confluence, or any workplace service.
- Do not install system software or add a new product dependency.
- Never read, print, log, commit, return, or store provider keys in frontend state.
- Weather facts come only from OpenWeather and Open-Meteo; there is no generated or deterministic planning-weather fallback.
- Every successful explicit analysis action makes exactly two Gemini requests: one budget request capped at 900 output tokens and one place request capped at 3,200 output tokens.
- The Gemini model defaults to `gemini-3.5-flash-lite`.
- Automated tests use fake provider transports or injected fakes and never consume real provider quota.
- Keep existing trips, travelers, expenses, selections, and itineraries intact.
- A refresh failure must leave the last successful persisted analysis unchanged.

## Review Focus

- A trip with zero traveler rows must estimate for one traveler rather than sending a zero-person request; Task 4 adds this test.
- Empty geocoding results, malformed weather payloads, and upstream failures must return only `weather_unavailable` while retaining saved data; Tasks 2 and 4 add these tests.
- Partial forecast coverage, cross-year trips, past trips, and leap days must map every requested date to either forecast or explicitly dated historical data; Task 2 adds these tests.
- A Gemini currency mismatch, reversed range, too many places, or invalid coordinates must return `invalid_provider_response` without partial persistence; Tasks 3 and 4 add these tests.
- A successful refresh must preserve selected places across case-only canonical-name changes while leaving genuinely new places unselected; Task 4 adds this test.

---

### Task 1: Persist departure city and planning profiles without changing existing trip rows

**Files:**

- Create: `backend/app/models/planning_profile.py`
- Modify: `backend/app/models/trip.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/trip.py`
- Modify: `backend/app/services/trip_service.py`
- Modify: `backend/tests/test_models.py`
- Modify: `backend/tests/test_planning.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**

- Produces: `TripPlanningProfile(trip_id, departure_city, weather_report, budget_report, weather_source, budget_model, analyzed_at)`.
- Produces: `Trip.departure_city -> str | None` and `Trip.planning_profile -> TripPlanningProfile | None`.
- Produces: required `TripCreate.departure_city: str` and returned `TripRead.departure_city: str | None`.
- Consumes: the existing `Trip`, `create_trip`, `list_trips`, and `get_trip` flows.

- [ ] **Step 1: Write failing persistence and schema tests**

Add tests that pin new-trip, legacy-trip, and cascade behavior:

```python
def test_create_trip_persists_departure_city_in_planning_profile(db):
    from app.models import TripPlanningProfile
    from app.schemas.trip import TripCreate
    from app.services.trip_service import create_trip

    user = make_user(db)
    trip = create_trip(
        db,
        user.id,
        TripCreate(
            name="Japan spring",
            departure_city="Delhi",
            destination="Kyoto",
            start_date=date(2027, 4, 4),
            number_of_days=5,
            currency="INR",
            travel_style="COMFORTABLE",
        ),
    )

    profile = db.get(TripPlanningProfile, trip.id)
    assert profile is not None
    assert profile.departure_city == "Delhi"
    assert profile.weather_report is None
    assert trip.departure_city == "Delhi"


def test_legacy_trip_without_profile_reads_null_departure_city(db):
    from app.models import Trip, User

    user = User(name="Legacy", email="legacy@example.test")
    trip = Trip(
        user=user,
        name="Existing trip",
        destination="Goa",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 3),
        number_of_days=3,
        base_currency="INR",
        travel_style="BUDGET",
        status="PLANNING",
    )
    db.add(trip)
    db.commit()

    assert trip.departure_city is None


def test_trip_create_requires_nonblank_departure_city():
    with pytest.raises(PydanticValidationError):
        TripCreate(
            name="Trip",
            departure_city="   ",
            destination="Goa",
            start_date=date(2027, 1, 1),
            number_of_days=2,
        )
```

- [ ] **Step 2: Run the focused tests and verify the new contract fails**

Run:

```bash
.venv/bin/pytest backend/tests/test_models.py backend/tests/test_planning.py -q
```

Expected: failures show that `TripPlanningProfile`, `departure_city`, and the relationship do not exist.

- [ ] **Step 3: Add the model, relationship, and exact request/read fields**

Create the profile with nullable reports because it exists before the first successful analysis:

```python
class TripPlanningProfile(Base):
    __tablename__ = "trip_planning_profiles"

    trip_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("trips.id", ondelete="CASCADE"),
        primary_key=True,
    )
    departure_city: Mapped[str] = mapped_column(String(200), nullable=False)
    weather_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    budget_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    weather_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    budget_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trip: Mapped["Trip"] = relationship(back_populates="planning_profile")
```

Add `planning_profile` with `cascade="all, delete-orphan"`, `single_parent=True`, and `uselist=False` to `Trip`. Add this compatibility property:

```python
@property
def departure_city(self) -> str | None:
    return self.planning_profile.departure_city if self.planning_profile else None
```

Strip `departure_city` with the same validator used for trip name and destination. Export the model from `app.models` so `Base.metadata.create_all()` creates only the new table on existing databases.

- [ ] **Step 4: Create the profile in the same transaction and eager-load it on reads**

Build the relationship before the existing single commit:

```python
trip.planning_profile = TripPlanningProfile(departure_city=payload.departure_city)
db.add(trip)
db.commit()
```

Add `selectinload(Trip.planning_profile)` to both list and single-trip queries. Add `departure_city` to `TripRead` so existing trips serialize it as `null`.

- [ ] **Step 5: Update existing backend trip fixtures with explicit departure cities and run tests**

Add a realistic `departure_city` to every `TripCreate` call in `backend/tests`, including lifecycle and archive payloads. Run:

```bash
.venv/bin/pytest backend/tests/test_models.py backend/tests/test_planning.py backend/tests/test_api.py -q
```

Expected: PASS, including legacy rows with no planning profile.

- [ ] **Step 6: Commit the persistence slice**

```bash
git add backend/app/models/planning_profile.py backend/app/models/trip.py backend/app/models/__init__.py backend/app/schemas/trip.py backend/app/services/trip_service.py backend/tests/test_models.py backend/tests/test_planning.py backend/tests/test_api.py
git commit -m "feat: persist trip planning profiles"
```

### Task 2: Replace deterministic weather with complete API weather and historical coverage

**Files:**

- Create: `backend/app/schemas/planning.py`
- Rewrite: `backend/app/providers/weather.py`
- Create: `backend/tests/test_weather_provider.py`
- Modify: `backend/tests/test_planning.py`

**Interfaces:**

- Produces: `async get_weather_report(destination: str, start_date: date, end_date: date, *, client: httpx.AsyncClient | None = None, today: date | None = None) -> WeatherReport`.
- Produces: `WeatherReport(location, current, daily, source, summary)` where each `DailyWeather` has `requested_date`, `source_date`, and `source` equal to `forecast` or `historical`.
- Produces: internal `WeatherProviderError` with a fixed message and no upstream details.
- Consumes: `TRIPWISE_OPENWEATHER_API_KEY`; Open-Meteo remains keyless.

- [ ] **Step 1: Define strict weather and planning value objects**

Add bounded Pydantic models to `schemas/planning.py`. Use these exact public shapes:

```python
class ResolvedLocation(BaseModel):
    name: str
    country_code: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone_offset_seconds: int


class CurrentWeather(BaseModel):
    observed_at: datetime
    condition: str
    description: str
    temperature_c: Decimal
    feels_like_c: Decimal
    minimum_c: Decimal
    maximum_c: Decimal
    humidity_percent: int = Field(ge=0, le=100)
    pressure_hpa: int = Field(gt=0)
    visibility_m: int = Field(ge=0)
    cloud_percent: int = Field(ge=0, le=100)
    wind_speed_kph: Decimal = Field(ge=0)
    wind_direction_degrees: int = Field(ge=0, le=360)
    rain_mm_1h: Decimal | None = Field(default=None, ge=0)
    snow_mm_1h: Decimal | None = Field(default=None, ge=0)
    sunrise_at: datetime
    sunset_at: datetime


class DailyWeather(BaseModel):
    requested_date: date
    source_date: date
    source: Literal["forecast", "historical"]
    minimum_c: Decimal
    maximum_c: Decimal
    representative_c: Decimal
    condition: str
    precipitation_probability_percent: int | None = Field(default=None, ge=0, le=100)
    precipitation_mm: Decimal | None = Field(default=None, ge=0)
    humidity_percent: int | None = Field(default=None, ge=0, le=100)
    maximum_wind_kph: Decimal = Field(ge=0)


class WeatherReport(BaseModel):
    location: ResolvedLocation
    current: CurrentWeather
    daily: list[DailyWeather]
    source: Literal["openweather", "openweather+open-meteo"]
    summary: str
```

- [ ] **Step 2: Write failing provider tests for complete parsing and date coverage**

Use `httpx.MockTransport` to assert calls to OpenWeather geocoding, current, five-day forecast, and Open-Meteo archive. The primary test must assert all current fields and ordered daily rows:

```python
assert report.location.name == "Delhi"
assert report.current.temperature_c == Decimal("28.4")
assert report.current.feels_like_c == Decimal("29.0")
assert report.current.pressure_hpa == 1012
assert report.current.visibility_m == 10000
assert report.current.cloud_percent == 0
assert report.current.wind_speed_kph == Decimal("18.0")
assert [row.requested_date for row in report.daily] == [
    date(2026, 10, 6),
    date(2026, 10, 7),
    date(2026, 10, 8),
]
assert report.daily[0].source == "forecast"
assert report.daily[-1].source == "historical"
assert report.daily[-1].source_date == date(2025, 10, 8)
```

Add focused tests for local-time forecast aggregation, a past trip using its actual archived dates, a December-to-January span, February 29 mapping to February 28 in a non-leap source year, empty geocoding results, malformed payloads, and 5xx responses.

- [ ] **Step 3: Run the new weather tests and verify they fail without API report support**

Run:

```bash
.venv/bin/pytest backend/tests/test_weather_provider.py -q
```

Expected: failures reference missing weather report models and `get_weather_report`.

- [ ] **Step 4: Implement geocoding, current parsing, and local-date forecast aggregation**

Use these provider URLs and request parameters:

```python
OPENWEATHER_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
```

Resolve one location with `q`, `limit=1`, and `appid`. Query current and forecast by `lat`, `lon`, `appid`, and `units=metric`. Convert wind metres per second to kilometres per hour with `Decimal("3.6")`. Aggregate forecast samples after applying the provider timezone offset; use minimum/maximum temperature, the sample nearest local noon as representative, the most frequent condition, maximum precipitation probability, average humidity, and maximum wind. Build `WeatherReport.summary` from the resolved name, current condition, temperature, humidity, and wind so dashboard compatibility text remains entirely API-sourced.

- [ ] **Step 5: Implement historical mapping and Open-Meteo grouping**

Compute the archive cutoff as `today - timedelta(days=5)`. For past trip dates at or before the cutoff, use the requested dates themselves. For future or too-recent dates, shift the complete uncovered span backward by whole years until every mapped date is at or before the cutoff. Map February 29 to February 28 only when the chosen source year is not a leap year. Group consecutive source dates into the minimum number of archive requests and request:

```text
temperature_2m_max,temperature_2m_min,temperature_2m_mean,
precipitation_sum,weather_code,wind_speed_10m_max
```

Send `timezone=auto` and translate WMO codes into condition text with a module-level mapping derived from the Open-Meteo documentation. Every row must retain both its requested date and actual source date.

- [ ] **Step 6: Remove the local hash fallback and normalize all failures**

Delete `_local_weather`, `_analysis`, `_score`, and their imports. Missing keys, no geocoding match, provider HTTP errors, and malformed JSON must raise `WeatherProviderError("weather provider unavailable")`, containing no URL, query parameters, response body, or key. Do not catch that exception to synthesize data.

- [ ] **Step 7: Run weather tests and commit**

Run:

```bash
.venv/bin/pytest backend/tests/test_weather_provider.py -q
.venv/bin/ruff check backend/app/providers/weather.py backend/app/schemas/planning.py backend/tests/test_weather_provider.py
```

Expected: PASS.

```bash
git add backend/app/schemas/planning.py backend/app/providers/weather.py backend/tests/test_weather_provider.py backend/tests/test_planning.py
git commit -m "feat: add complete trip weather reports"
```

### Task 3: Add isolated Gemini budget and place providers with strict token ceilings

**Files:**

- Modify: `backend/app/providers/gemini.py`
- Create: `backend/app/providers/gemini_planning.py`
- Modify: `backend/app/schemas/planning.py`
- Modify: `backend/tests/test_gemini_provider.py`
- Create: `backend/tests/test_gemini_planning.py`

**Interfaces:**

- Produces: `GeminiProvider.generate_structured(*, instructions: str, input_messages: list[dict[str, Any]], text_format: type[BaseModel], max_output_tokens: int | None = None) -> BaseModel`.
- Produces: `GeminiPlanningProvider.estimate_budget(facts: BudgetFacts) -> BudgetReport`.
- Produces: `GeminiPlanningProvider.discover_places(facts: PlaceFacts) -> list[PlaceSuggestion]`.
- Produces: `GeminiPlanningProvider.model: str` and `close() -> None`.
- Produces: `build_gemini_planning_provider() -> GeminiPlanningProvider`, which fails safely when Gemini is disabled or unconfigured.
- Produces: internal `PlanningProviderUnavailable` for configuration/network failures and `InvalidPlanningResponse` for malformed or schema-invalid model output.
- Consumes: only the fields allowed by the design spec and the existing backend-only Gemini key/model settings.

- [ ] **Step 1: Write failing tests for Gemini's token configuration**

Extend the existing mock-transport test:

```python
result = provider.generate_structured(
    instructions="Return only the requested facts.",
    input_messages=[{"role": "user", "content": '{"destination":"Kyoto"}'}],
    text_format=Greeting,
    max_output_tokens=900,
)

assert captured_payload["generationConfig"]["maxOutputTokens"] == 900
assert result.greeting == "Hello from Gemini"
```

Also verify that omitting the argument leaves `maxOutputTokens` out so itinerary and summary behavior is unchanged.

- [ ] **Step 2: Add strict facts and output schemas**

Add these public facts and report types to `schemas/planning.py`:

```python
class EstimateRange(BaseModel):
    minimum: Decimal = Field(ge=0)
    typical: Decimal = Field(ge=0)
    maximum: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "EstimateRange":
        if not self.minimum <= self.typical <= self.maximum:
            raise ValueError("estimate range must be ordered")
        return self


class BudgetCategories(BaseModel):
    flights: EstimateRange
    accommodation: EstimateRange
    food: EstimateRange
    local_transport: EstimateRange
    tickets: EstimateRange
    activities: EstimateRange


class BudgetReport(BaseModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    traveler_count: int = Field(ge=1)
    number_of_days: int = Field(ge=1)
    categories: BudgetCategories
    total: EstimateRange


class PlaceSuggestion(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=240)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    recommended_days: Decimal = Field(ge=Decimal("0.5"))
    best_for: list[str] = Field(max_length=4)
    relevance_score: Decimal = Field(ge=0, le=10)
```

Define `GeminiBudgetResult(currency, categories)` and `GeminiPlacesResult(places)` as provider-output schemas with `ConfigDict(extra="forbid")`; constrain the places list to 1–20 items. Define `BudgetFacts` with exactly departure city, destination, start date, days, traveler count, style, and currency. Define `PlaceFacts` with exactly destination, days, style, and `maximum_results=20`. Strip place names, descriptions, and tags before enforcing non-empty lengths.

- [ ] **Step 3: Write failing prompt-isolation and validation tests**

Use a recording fake `GeminiProvider` and assert the decoded JSON has exact keys:

```python
assert set(budget_payload) == {
    "departure_city",
    "destination",
    "start_date",
    "number_of_days",
    "traveler_count",
    "travel_style",
    "currency",
}
assert budget_call.max_output_tokens == 900
assert set(place_payload) == {
    "destination",
    "number_of_days",
    "travel_style",
    "maximum_results",
}
assert place_call.max_output_tokens == 3200
```

Assert the budget total is computed by the backend from six category ranges. Add rejection tests for the wrong currency, reversed ranges, 21 places, a place above the trip duration, invalid coordinates, descriptions over 240 characters, and more than four tags. Add a deduplication test proving `"Red Fort"` and `"red fort"` produce one result while preserving first-result order.

- [ ] **Step 4: Run Gemini planning tests and verify the missing adapter failures**

Run:

```bash
.venv/bin/pytest backend/tests/test_gemini_provider.py backend/tests/test_gemini_planning.py -q
```

Expected: failures show missing token configuration and planning provider interfaces.

- [ ] **Step 5: Implement the isolated provider methods**

Add optional `maxOutputTokens` to `generationConfig` only when supplied. In `gemini_planning.py`, send one compact JSON message per method and use separate instructions:

```python
BUDGET_INSTRUCTIONS = (
    "Estimate only the requested complete-trip budget for the complete travel party in the "
    "requested currency. Flights must be round-trip economy for the complete group. Return "
    "structured category numbers only; do not add places, itinerary, weather, or prose."
)

PLACE_INSTRUCTIONS = (
    "Return only relevant visitable places for the destination in relevance order. "
    "Return at most the requested count; do not add budget, weather, flights, or itinerary."
)
```

Call synchronous `GeminiProvider.generate_structured` through `asyncio.to_thread` so budget and place methods can run concurrently. Validate the returned currency against `facts.currency`; calculate `minimum`, `typical`, and `maximum` by summing that field across `flights`, `accommodation`, `food`, `local_transport`, `tickets`, and `activities`, starting from `Decimal("0")`. Enforce `recommended_days <= facts.number_of_days`, deduplicate names with `name.casefold()`, and reject a response if deduplication leaves no place. Wrap HTTP/configuration failures as `PlanningProviderUnavailable`; wrap empty structured output, JSON/schema validation, currency mismatch, and post-validation failures as `InvalidPlanningResponse`. Neither exception includes upstream bodies, URLs, prompts, or keys. Build the default provider only when Gemini is enabled and both key and model are configured; raise `PlanningProviderUnavailable` with no key value when configuration is missing.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
.venv/bin/pytest backend/tests/test_gemini_provider.py backend/tests/test_gemini_planning.py -q
.venv/bin/ruff check backend/app/providers/gemini.py backend/app/providers/gemini_planning.py backend/app/schemas/planning.py backend/tests/test_gemini_provider.py backend/tests/test_gemini_planning.py
```

Expected: PASS.

```bash
git add backend/app/providers/gemini.py backend/app/providers/gemini_planning.py backend/app/schemas/planning.py backend/tests/test_gemini_provider.py backend/tests/test_gemini_planning.py
git commit -m "feat: add isolated Gemini planning requests"
```

### Task 4: Orchestrate and atomically persist analysis behind safe API contracts

**Files:**

- Rewrite: `backend/app/services/planning_service.py`
- Modify: `backend/app/core/exceptions.py`
- Modify: `backend/app/models/place.py`
- Modify: `backend/app/schemas/place.py`
- Modify: `backend/app/schemas/planning.py`
- Modify: `backend/app/api/trips.py`
- Modify: `backend/app/api/places.py`
- Delete: `backend/app/providers/catalog.py`
- Modify: `backend/app/seed.py`
- Rewrite: `backend/tests/test_planning.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_seed.py`

**Interfaces:**

- Produces: `AnalyzeTripRequest(departure_city: str | None = None)`.
- Produces: `async analyze_trip(db, trip, payload, *, weather_fetcher: WeatherFetcher | None = None, planning_provider: PlanningAIProvider | None = None) -> AnalysisResponse`.
- Produces: `get_analysis(db, trip) -> AnalysisResponse` without provider access.
- Produces: `POST /api/v1/trips/{trip_id}/analyze` and `GET /api/v1/trips/{trip_id}/analysis`.
- Produces: `ProviderError(code)` as HTTP 502 with `{"detail":{"code":"<safe-code>"}}`.
- Consumes: Task 1 profile persistence, Task 2 weather reports, and Task 3 Gemini provider methods.

- [ ] **Step 1: Write failing service tests for concurrency and atomic success**

Create fake async weather and planning providers that append `weather`, `budget`, and `places` to a call log. Gate each fake on a shared `asyncio.Event`, start `analyze_trip` as a task, and assert all three operations started before releasing the event. Assert one successful result persists:

```python
assert call_log == {"weather", "budget", "places"}
assert result.status == "READY"
assert result.budget.total.typical == Decimal("125000")
assert result.weather.current.condition == "Clear"
assert len(result.places) == 2
assert trip.planning_profile.weather_source == "openweather+open-meteo"
assert trip.planning_profile.budget_model == "gemini-3.5-flash-lite"
assert trip.weather_score is None
assert trip.weather_rating is None
assert trip.estimated_cost == Decimal("125000")
```

Count the fake provider's methods and assert exactly one budget and one place call. For a trip with no traveler rows, assert `BudgetFacts.traveler_count == 1`.

- [ ] **Step 2: Write failing tests for failure preservation and selection refresh**

First save a successful analysis and select a place. Then inject each failure independently and assert `weather_report`, `budget_report`, place IDs, selected flags, and trip summary fields are byte-for-byte unchanged. Add a successful refresh where `"Red Fort"` becomes `"red fort"`; assert it stays selected while `"India Gate"` is unselected.

Add invalid-output tests where the provider raises Pydantic validation errors. They must become `invalid_provider_response`, not a raw validation message.

- [ ] **Step 3: Write failing API tests for legacy departure and safe errors**

Pin these contracts through `TestClient`:

```python
missing_departure = client.post(f"/api/v1/trips/{legacy_trip.id}/analyze", json={})
assert missing_departure.status_code == 422

failed = client.post(
    f"/api/v1/trips/{trip_id}/analyze",
    json={"departure_city": "Delhi"},
)
assert failed.status_code == 502
assert failed.json() == {"detail": {"code": "budget_unavailable"}}
assert "key" not in failed.text.lower()

saved = client.get(f"/api/v1/trips/{trip_id}/analysis")
assert saved.status_code == 200
```

Also assert an unanalyzed profile returns 404 and that a GET analysis call leaves fake-provider call counts at zero.

Update the complete lifecycle API test to monkeypatch `app.services.planning_service.get_weather_report` and `build_gemini_planning_provider` with valid fakes before it POSTs `/analyze`; this keeps the integration flow complete without using environment credentials.

- [ ] **Step 4: Run focused tests and verify the current destructive/fallback behavior fails**

Run:

```bash
.venv/bin/pytest backend/tests/test_planning.py backend/tests/test_api.py -q
```

Expected: failures show the old catalog, fixed budget, score response, missing read endpoint, and unsafe/non-atomic behavior.

- [ ] **Step 5: Implement safe stage errors and the new response contract**

Make `ProviderError` status 502 and accept only these codes:

```python
ProviderCode = Literal[
    "weather_unavailable",
    "budget_unavailable",
    "places_unavailable",
    "invalid_provider_response",
]

class ProviderError(TripWiseError):
    status_code = 502

    def __init__(self, code: ProviderCode):
        super().__init__({"code": code})
```

Change `TripWiseError.detail` from `str` to `str | dict[str, str]` so the existing application handler serializes both normal errors and the fixed provider code object.

Define `PlaceRead` with `relevance_score` instead of estimated costs and weather score. Add a `Place.relevance_score` property returning `overall_score`; persist the Gemini relevance value into both `overall_score` and the legacy required `weather_score` column while never exposing the latter. Define `AnalysisResponse` with `weather`, `budget`, `places`, `weather_source`, `budget_model`, `analyzed_at`, and `status`.

- [ ] **Step 6: Implement concurrent fetch, validation, then one transaction**

Resolve departure city from the request or existing profile. Resolve `weather_fetcher or get_weather_report` at call time and construct `planning_provider or build_gemini_planning_provider()` at call time so tests can inject fakes without altering production behavior. Run the operations together with this exact shape so every started call finishes before owned clients close:

```python
weather_result, budget_result, places_result = await asyncio.gather(
    weather_operation(),
    active_planning_provider.estimate_budget(budget_facts),
    active_planning_provider.discover_places(place_facts),
    return_exceptions=True,
)
```

Translate exceptions at the stage boundary without including exception text. API tests may monkeypatch `build_gemini_planning_provider` and `get_weather_report`; service tests pass the two keyword arguments directly.

Define the service boundary explicitly:

```python
class PlanningAIProvider(Protocol):
    model: str

    async def estimate_budget(self, facts: BudgetFacts) -> BudgetReport:
        raise NotImplementedError

    async def discover_places(self, facts: PlaceFacts) -> list[PlaceSuggestion]:
        raise NotImplementedError
```

Map `InvalidPlanningResponse` to `invalid_provider_response`, budget/places `PlanningProviderUnavailable` to the matching stage code, and every weather exception to `weather_unavailable`.

Only after all results validate:

```python
selected_names = {place.name.casefold() for place in trip.places if place.selected}
profile.weather_report = weather.model_dump(mode="json")
profile.budget_report = budget.model_dump(mode="json")
profile.weather_source = weather.source
profile.budget_model = planning_provider.model
profile.analyzed_at = utc_now()
trip.weather_score = None
trip.weather_rating = None
trip.weather_summary = weather.summary
trip.estimated_cost_min = budget.total.minimum
trip.estimated_cost = budget.total.typical
trip.estimated_cost_max = budget.total.maximum
```

Delete and recreate candidate place rows inside the same transaction, preserving `selected` by case-folded name. Commit once; on any database exception, roll back and re-raise. Close only a provider instance created inside `analyze_trip`; injected test providers remain owned by their caller. `get_analysis` rebuilds the Pydantic response from profile JSON plus persisted places and never imports or calls a provider.

- [ ] **Step 7: Add the API routes and remove the catalog path**

Accept an empty request body only when the trip already has a departure city. Add `GET /analysis`. Keep place selection independent. Remove all imports of `get_candidate_places`, delete `providers/catalog.py`, remove fixed budget multipliers/constants, and order place reads by relevance.

- [ ] **Step 8: Make the seed test provider-safe**

Give `seed_demo` optional `weather_fetcher` and `planning_provider` keyword arguments and pass them to `analyze_trip`. Set the showcase trip's explicit departure city to `Bengaluru`. In `test_seed.py`, define a local `SeedPlanningProvider` whose `model` is `"test-gemini"`, whose async budget method returns six valid category ranges and a computed total, and whose async places method returns three valid `PlaceSuggestion` objects. Inject an async weather function that returns a valid `WeatherReport`. Never rely on environment keys. Update the assertion from a weather score to a non-null persisted weather report and departure city.

- [ ] **Step 9: Run the complete backend suite and commit**

Run:

```bash
.venv/bin/pytest backend/tests -q
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
```

Expected: all backend tests pass and no test contacts a real provider.

```bash
git add backend/app/services/planning_service.py backend/app/core/exceptions.py backend/app/models/place.py backend/app/schemas/place.py backend/app/schemas/planning.py backend/app/api/trips.py backend/app/api/places.py backend/app/seed.py backend/tests/test_planning.py backend/tests/test_api.py backend/tests/test_seed.py
git rm backend/app/providers/catalog.py
git commit -m "feat: persist atomic provider planning analysis"
```

### Task 5: Add frontend analysis contracts, cached reads, and required departure city

**Files:**

- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/queryKeys.ts`
- Modify: `frontend/src/lib/queries.ts`
- Modify: `frontend/src/pages/NewTripPage.tsx`
- Modify: `frontend/tests/planning-flow.test.tsx`
- Modify: `frontend/tests/trip-actions.test.tsx`

**Interfaces:**

- Produces: TypeScript `WeatherReport`, `BudgetReport`, `PlanningAnalysis`, and slim `Place` types matching Task 4 JSON.
- Produces: `queryKeys.analysis(tripId)` and `usePlanningAnalysis(tripId)` returning `PlanningAnalysis | null` on a first-analysis 404.
- Produces: trip creation payload with required `departure_city`.
- Consumes: the existing API client, form, and TanStack Query setup.

- [ ] **Step 1: Write failing trip-creation and cached-read tests**

Extend the creation interaction to fill `Departure city` and assert the POST body:

```typescript
await user.type(screen.getByLabelText(/departure city/i), 'Delhi')
await user.click(screen.getByRole('button', { name: /create trip/i }))

expect(calls[0].body).toMatchObject({
  departure_city: 'Delhi',
  destination: 'Sri Lanka',
})
```

Add a query test proving `/trips/trip-1/analysis` is fetched once on mount and its 404 becomes an empty analysis state instead of a full-page error. Assert no POST request is made during render.

- [ ] **Step 2: Run the focused frontend test and verify it fails**

Run:

```bash
npm --prefix frontend test -- planning-flow.test.tsx
```

Expected: failures show the missing departure field and missing analysis query.

- [ ] **Step 3: Add exact frontend contracts and cached query behavior**

Define the report types with API field names. The budget categories are `flights`, `accommodation`, `food`, `local_transport`, `tickets`, and `activities`; each contains string `minimum`, `typical`, and `maximum` values. Daily weather uses `source: 'forecast' | 'historical'`, requested/source dates, temperatures, condition, precipitation, humidity, and wind.

Implement the read query with an explicit 404 conversion:

```typescript
export function usePlanningAnalysis(tripId: string) {
  return useQuery({
    queryKey: queryKeys.analysis(tripId),
    queryFn: async () => {
      try {
        return await api.get<PlanningAnalysis>(`/trips/${tripId}/analysis`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
    enabled: !!tripId,
    retry: false,
  })
}
```

- [ ] **Step 4: Add and validate the required form field**

Add `departure_city: z.string().trim().min(1)`, register it beside destination, include it unchanged in the create payload, and show `Departure city is required.` for an empty value. Add `departure_city` to every typed `Trip` fixture, including `activeTrip` in `trip-actions.test.tsx`.

- [ ] **Step 5: Run tests, typecheck, and commit**

Run:

```bash
npm --prefix frontend test -- planning-flow.test.tsx
npm --prefix frontend run typecheck
```

Expected: PASS.

```bash
git add frontend/src/lib/types.ts frontend/src/lib/queryKeys.ts frontend/src/lib/queries.ts frontend/src/pages/NewTripPage.tsx frontend/tests/planning-flow.test.tsx frontend/tests/trip-actions.test.tsx
git commit -m "feat: add planning analysis frontend contracts"
```

### Task 6: Render complete weather, budget, and places with refresh-safe interactions

**Files:**

- Create: `frontend/src/components/planning/WeatherReport.tsx`
- Create: `frontend/src/components/planning/BudgetReport.tsx`
- Create: `frontend/src/components/planning/PlaceRecommendations.tsx`
- Create: `frontend/src/lib/maps.ts`
- Rewrite: `frontend/src/pages/PlanPage.tsx`
- Modify: `frontend/src/styles.css`
- Rewrite: `frontend/tests/planning-flow.test.tsx`

**Interfaces:**

- Produces: `googleMapsSearchUrl(placeName: string, destination: string) -> string`.
- Produces: focused, presentation-only weather, budget, and place components.
- Produces: Plan-page orchestration that POSTs only on explicit button clicks and retains cached analysis on mutation failure.
- Consumes: Task 5 types/query and the existing `/places/select` mutation.

- [ ] **Step 1: Write failing display tests for every report section**

Supply a persisted mixed-source analysis fixture and assert the page displays resolved location, current observation time, analysis timestamp, weather source, feels-like, high/low, humidity, pressure, visibility, cloud cover, wind, sunrise/sunset, forecast dates, and the historical heading with actual source year.

For budget, assert the group typical total, min/max total, all six category rows, traveler count, Gemini model label, and `Gemini estimate—not a live quote`. For places, assert description, duration, tags, relevance, and the map link:

```typescript
const mapLink = await screen.findByRole('link', { name: /open red fort in google maps/i })
expect(mapLink).toHaveAttribute(
  'href',
  'https://www.google.com/maps/search/?api=1&query=Red%20Fort%20Delhi',
)
expect(mapLink).toHaveAttribute('target', '_blank')
expect(mapLink).toHaveAttribute('rel', expect.stringContaining('noopener'))
expect(screen.queryByText(/per-place estimate/i)).not.toBeInTheDocument()
```

- [ ] **Step 2: Write failing interaction tests for legacy trips and safe refreshes**

Cover these flows:

- a legacy trip shows a required departure-city input and POSTs `{"departure_city":"Mumbai"}`;
- a new trip with stored departure city POSTs an empty object;
- the loading state says weather, budget, and places are being fetched;
- a `budget_unavailable` mutation error shows a budget retry message while the old report remains visible;
- refreshed results preserve selected checkboxes and saving selection remains a separate POST;
- initial page render performs GETs only.

- [ ] **Step 3: Run the focused tests and verify current UI failures**

Run:

```bash
npm --prefix frontend test -- planning-flow.test.tsx
```

Expected: failures reference missing report details, legacy departure input, map links, and refresh retention.

- [ ] **Step 4: Implement the keyless Google Maps helper and presentation components**

Build the URL only from persisted names:

```typescript
export function googleMapsSearchUrl(placeName: string, destination: string): string {
  const query = encodeURIComponent(`${placeName} ${destination}`)
  return `https://www.google.com/maps/search/?api=1&query=${query}`
}
```

Keep components free of network calls. Render unavailable optional weather measures as `—`, label every historical row with its source date, format money with the existing helper, and use semantic tables or definition lists so minimum/typical/maximum columns remain accessible on narrow screens.

- [ ] **Step 5: Implement Plan-page orchestration without auto-analysis**

Use `useTrip`, `usePlanningAnalysis`, and local selection state. On successful analysis, set both the analysis and places caches, invalidate the trip query, and replace selection from the response. When saving selection, merge the returned selected IDs into the cached complete place list instead of replacing that list with only selected rows. On failure, never clear or overwrite the analysis query data. Derive the safe message from `ApiError.details`:

```typescript
const retryMessages: Record<string, string> = {
  weather_unavailable: 'Weather providers could not be reached. Your saved analysis is still here.',
  budget_unavailable: 'Gemini could not estimate the budget. Your saved analysis is still here.',
  places_unavailable: 'Gemini could not suggest places. Your saved analysis is still here.',
  invalid_provider_response: 'A provider returned invalid data. Your saved analysis is still here.',
}
```

Use articles rather than wrapping the whole place card in a label so clicking **Open in Google Maps** never toggles the checkbox.

- [ ] **Step 6: Add responsive planning styles and run frontend checks**

Replace the two-card `.plan-metrics` styling with focused classes for current-weather details, daily rows, budget table, source badges, place cards, and the sticky selection bar. Keep the existing Fraunces/Manrope design language and add one-column breakpoints below 900px.

Run:

```bash
npm --prefix frontend test -- planning-flow.test.tsx
npm --prefix frontend run typecheck
npm --prefix frontend run lint
```

Expected: PASS.

- [ ] **Step 7: Commit the Plan page**

```bash
git add frontend/src/components/planning/WeatherReport.tsx frontend/src/components/planning/BudgetReport.tsx frontend/src/components/planning/PlaceRecommendations.tsx frontend/src/lib/maps.ts frontend/src/pages/PlanPage.tsx frontend/src/styles.css frontend/tests/planning-flow.test.tsx
git commit -m "feat: show provider-backed trip planning reports"
```

### Task 7: Remove weather-fit UI and update project documentation

**Files:**

- Modify: `frontend/src/pages/OverviewPage.tsx`
- Modify: `frontend/tests/planning-flow.test.tsx`
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**

- Produces: overview cards backed only by `weather_summary` and persisted Gemini total estimates.
- Produces: setup documentation that accurately describes provider-backed planning and manual refresh behavior.
- Consumes: trip summary compatibility fields from Task 4.

- [ ] **Step 1: Write a failing overview regression test**

Render an analyzed trip and assert:

```typescript
expect(screen.getByText(/current weather/i)).toBeInTheDocument()
expect(screen.getByText(/clear.*28/i)).toBeInTheDocument()
expect(screen.queryByText(/weather fit/i)).not.toBeInTheDocument()
expect(screen.queryByText(/\/10/)).not.toBeInTheDocument()
```

- [ ] **Step 2: Run the focused test and verify the old score UI fails it**

Run:

```bash
npm --prefix frontend test -- planning-flow.test.tsx
```

Expected: the existing **Weather fit** label causes the test to fail.

- [ ] **Step 3: Replace obsolete overview scores and update documentation**

Label the overview stat **Current weather**, use the API-sourced `weather_summary` as its value, and remove all reads of `weather_score` and `weather_rating` from UI code.

Update README sections for planning, provider responsibilities, configuration, REST routes, and demo workflow. Document that analysis requires configured OpenWeather and Gemini providers, uses Open-Meteo automatically for historical rows, makes two Gemini requests only after a button press, persists results, and uses keyless Google Maps search links. Change `.env.example` to recommend `TRIPWISE_WEATHER_PROVIDER=openweather` without inserting a key.

- [ ] **Step 4: Run documentation guards and frontend checks**

Run:

```bash
rg -n "Weather fit|deterministic weather|fixed budget|providers\.catalog|STYLE_MULTIPLIER|daily_per_person|_local_weather" frontend/src backend/app README.md
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run lint
```

Expected: the search returns no stale planning implementation or documentation; all frontend checks pass.

- [ ] **Step 5: Commit compatibility UI and documentation**

```bash
git add frontend/src/pages/OverviewPage.tsx frontend/tests/planning-flow.test.tsx README.md .env.example
git commit -m "docs: describe provider-backed planning"
```

### Task 8: Verify the full application and one real disposable trip

**Files:**

- Modify only files required to fix failures found by these verification steps.

**Interfaces:**

- Verifies: backend contracts, frontend behavior, provider isolation, live configured providers, persistence, and cleanup.
- Consumes: all prior tasks and the already configured ignored `backend/.env` without printing it.

- [ ] **Step 1: Run the complete automated release gate**

Run:

```bash
.venv/bin/pytest backend/tests
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: every command exits zero. Fix failures at their owning layer and rerun the failing command before continuing.

- [ ] **Step 2: Prove automated tests did not depend on real credentials**

Run the provider suites with provider environment values explicitly blanked for the child process:

```bash
TRIPWISE_OPENWEATHER_API_KEY= TRIPWISE_GEMINI_API_KEY= TRIPWISE_GEMINI_ENABLED=false .venv/bin/pytest backend/tests/test_weather_provider.py backend/tests/test_gemini_planning.py backend/tests/test_planning.py -q
```

Expected: PASS through mock transports and injected fakes.

- [ ] **Step 3: Perform one real synthetic end-to-end analysis without exposing secrets**

With the existing backend and frontend running on ports 8000 and 5173, create a uniquely named synthetic trip through the UI with departure city, destination, future dates, one traveler, and no personal data. Click **Analyze trip** once. Verify:

- the Plan page shows current conditions and forecast or explicitly labeled historical rows;
- six budget categories include round-trip group flights;
- no more than 20 places appear;
- a Google Maps link contains an encoded place/destination query;
- reloading the page restores the same report without showing a new analysis loading state;
- the browser network panel shows one analysis POST and two Gemini provider operations are confirmed by backend fake-counter coverage, not by logging credentials or provider bodies.

- [ ] **Step 4: Delete only the synthetic trip and verify cleanup**

Use the app's delete action for the uniquely named synthetic trip. Confirm it no longer appears on the dashboard and that existing personal trips are unchanged. Do not delete or rewrite the SQLite database.

- [ ] **Step 5: Inspect the final diff and commit verification fixes if any**

Run:

```bash
git status --short
git diff --check
git log --oneline -8
```

If verification required code changes, stage only those explicit files and commit them with:

```bash
git commit -m "fix: complete planning analysis verification"
```

If the working tree is clean, do not create an empty commit.
