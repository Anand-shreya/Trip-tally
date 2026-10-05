# Gemini Planning Analysis Design

## Purpose

Replace TripWise's hardcoded planning catalog and fixed budget formula with a provider-backed planning report. The Plan page must show detailed weather, a flight-inclusive destination budget, and up to 20 relevant places with Google Maps links. Weather comes only from weather APIs. Budget and place discovery come from two narrowly scoped Gemini requests.

## Goals

- Show current conditions and relevant trip-date weather in a complete, clearly sourced report.
- Use forecast data when the trip falls within the weather provider's forecast window.
- Use the most recent matching historical calendar period available from Open-Meteo for trip dates that the forecast cannot cover.
- Ask Gemini only for a compact budget estimate in the budget request.
- Ask Gemini only for relevant destination places in the place request.
- Include round-trip economy flights from a required departure city.
- Include accommodation, food, local transport, tickets, and activities in the budget.
- Return no more than 20 places.
- Provide a keyless Google Maps search link for each place.
- Persist the last successful report so page loads do not consume Gemini tokens.
- Preserve the last successful report when a refresh fails.
- Remove destination-specific catalogs and fixed price constants from the planning path.

## Non-goals

- Booking flights, hotels, activities, or transport.
- Claiming that Gemini estimates are live quotes.
- Using Google Places, Geocoding, or Maps JavaScript APIs.
- Generating weather with Gemini.
- Adding a fabricated or deterministic planning fallback.
- Sending traveler names, email addresses, expenses, or the user's entered budget to Gemini.
- Automatically refreshing analysis when the Plan page loads.

## Provider Strategy

An explicit **Analyze trip** or **Refresh analysis** action starts three independent operations concurrently:

1. A weather operation using OpenWeather and Open-Meteo.
2. A Gemini budget operation.
3. A Gemini place-discovery operation.

The two Gemini operations remain separate so each prompt contains only the context needed for its result. The backend does not issue follow-up Gemini requests. A read, route selection, or page refresh never calls Gemini.

All three results must validate before TripWise replaces the persisted report. If one operation fails, the request returns a safe provider error and the last successful report and place selection remain unchanged.

## Weather Report

### Location resolution

Use OpenWeather geocoding to resolve the trip destination to a concrete latitude, longitude, display name, and country code. Country-only inputs may resolve to a capital or representative location; the UI must display the resolved location so the scope is not misleading.

### Current conditions

Use OpenWeather current conditions for:

- observation time;
- condition and description;
- temperature and feels-like temperature;
- minimum and maximum temperature;
- humidity and atmospheric pressure;
- visibility;
- cloud cover;
- wind speed and direction;
- rain or snow volume when present;
- sunrise and sunset;
- provider timezone offset.

### Forecast

Use OpenWeather's five-day forecast for each trip date that falls inside its available horizon. Aggregate three-hour samples in the resolved location's local time into daily rows containing:

- date;
- minimum, maximum, and representative temperature;
- dominant condition;
- maximum precipitation probability;
- average humidity;
- maximum wind speed.

Only rows relevant to the trip date range are shown. Current conditions remain separately labeled. If the forecast covers only part of the trip, keep those forecast rows and fill only the uncovered dates from historical data.

### Historical fallback

For every trip date outside the forecast horizon, query Open-Meteo's archive API for the most recent prior occurrence of the same calendar date for which archive data is available at the resolved coordinates. This is normally the matching period in the previous year, but the implementation moves farther back when necessary so it never presents future or unavailable data as historical. February 29 maps to February 28 in the selected non-leap year. A trip spanning a year boundary preserves its day order and uses the latest complete matching historical span.

Historical daily rows contain:

- historical date and corresponding requested trip date;
- minimum, maximum, and mean temperature;
- precipitation total;
- dominant weather code translated using the API's documented WMO code table;
- maximum wind speed.

Every daily row carries its source and source date. Historical rows are grouped under **Typical weather based on the most recent matching historical period**, with the actual source year displayed. They must not be called a forecast. A partially covered trip may therefore show a forecast group followed by a clearly separated historical group.

### Failure behavior

Weather API failures do not fall back to generated or deterministic weather. The backend raises a safe `weather_unavailable` provider error without including API keys, upstream URLs, or response bodies. A previously saved weather report remains visible.

## Gemini Budget Request

### Input

Send only:

- departure city;
- destination;
- start date;
- number of days;
- traveler count;
- travel style;
- requested currency.

Do not send traveler identities, the user's entered budget, weather, places, itinerary, expenses, or prose-generation instructions.

### Output schema

Gemini returns numeric minimum, typical, and maximum estimates for the complete travel party and complete trip for:

- round-trip economy flights for the complete group;
- accommodation;
- food;
- local transport;
- tickets;
- activities.

It also returns the requested currency code and no narrative text. Every amount must be non-negative, and each category must satisfy `minimum <= typical <= maximum`.

The backend verifies that the response currency exactly matches the requested currency, then computes the overall minimum, typical, and maximum by summing validated category values. Gemini does not provide authoritative totals. These are planning estimates, not quotes.

### Token constraints

- One request per explicit analysis action.
- Compact JSON input with no duplicated labels or user-facing prose.
- Strict structured JSON response.
- `maxOutputTokens` capped at 900.
- Model defaults to `gemini-3.5-flash-lite`.

## Gemini Place Request

### Input

Send only:

- destination;
- number of trip days;
- travel style;
- maximum result count of 20.

Do not send departure city, budget, weather, traveler identities, expenses, or itinerary history.

### Output schema

Gemini returns between 1 and 20 places. Each place contains:

- canonical name;
- concise description capped at 240 characters;
- latitude and longitude;
- recommended days;
- up to four `best_for` tags;
- relevance score from 0 to 10.

The backend validates coordinate ranges, result count, text lengths, non-empty names, recommended duration from 0.5 days through the full trip length, and score bounds. Duplicate names are removed case-insensitively while preserving Gemini's order. The backend stores no invented replacement when the result is invalid.

Existing place cost fields remain zero and are removed from the Plan page because the budget request owns cost estimation. `overall_score` stores Gemini's relevance score. The legacy non-null `weather_score` column stores the same provider-supplied relevance value only as a database compatibility value; it is omitted from the new API and UI and is never presented as weather fitness. No weather-fit score is calculated. The trip-level legacy `weather_score` and `weather_rating` fields are cleared, while `weather_summary` is synchronized from the API-sourced current conditions for dashboard compatibility.

### Token constraints

- One request per explicit analysis action.
- Strict structured JSON response.
- Descriptions capped at 240 characters.
- Four tags maximum.
- Twenty places maximum.
- `maxOutputTokens` capped at 3,200.

## Google Maps Links

TripWise does not call a Google Maps API. The frontend builds an official keyless search URL:

`https://www.google.com/maps/search/?api=1&query=<encoded place name and destination>`

The query is derived from the persisted Gemini place name and trip destination. Links open in a new tab with `noopener` and `noreferrer`. This adds no Google API key, billing requirement, network request during analysis, or AI token usage.

## Persistence

Add a one-to-one `TripPlanningProfile` table rather than altering existing trip rows. This preserves the current SQLite data and allows `create_all` to add the new table safely.

The table contains:

- `trip_id`, primary key and cascading foreign key;
- `departure_city`;
- `weather_report`, JSON;
- `budget_report`, JSON;
- `weather_source`;
- `budget_model`;
- `analyzed_at`.

New trip creation requires a departure city and creates the profile in the same transaction. Existing trips have no profile initially; their Plan page requests a departure city before analysis and creates the profile through the analysis request.

The existing trip `weather_summary` and estimated-cost columns remain synchronized with the new report for dashboard compatibility. The obsolete trip weather score/rating fields are cleared. Places continue to use the existing `places` table.

The analysis transaction begins only after all provider responses validate. It then:

1. upserts the planning profile;
2. replaces the trip's place rows, preserving `selected` for case-insensitive canonical-name matches and leaving newly suggested places unselected;
3. updates the trip summary weather and budget fields;
4. marks the trip ready;
5. commits once.

Any database error rolls back all planning changes.

## API Contracts

### Trip creation and reads

`POST /api/v1/trips` accepts a required `departure_city` for new trips.

Trip reads include `departure_city: string | null`. Existing trips return `null` until the user supplies it.

### Analysis mutation

`POST /api/v1/trips/{trip_id}/analyze` accepts:

```json
{
  "departure_city": "Delhi"
}
```

The field is optional when the planning profile already has a departure city. It is required for legacy trips without a profile.

The response includes the complete persisted weather report, budget breakdown, places, source metadata, and status.

### Analysis read

`GET /api/v1/trips/{trip_id}/analysis` returns the last successful report without contacting any provider. It returns `404` when analysis has never succeeded.

### Provider errors

Provider failures use `502` with a fixed safe detail object identifying only the failed stage:

- `weather_unavailable`;
- `budget_unavailable`;
- `places_unavailable`;
- `invalid_provider_response`.

No API key, Gemini prompt, upstream request URL, response body, or request identifier enters the browser response or stored error.

## Plan Page

### Before analysis

- New trips already have a departure city.
- Legacy trips show a required departure-city input beside **Analyze trip**.
- Explain that weather comes from weather APIs and estimates/places come from Gemini.

### Weather section

- Resolved location and source timestamp.
- Prominent current temperature and condition.
- Feels-like, high/low, humidity, wind, visibility, pressure, cloud cover, sunrise, and sunset.
- Daily forecast rows when available.
- Clearly separated forecast and historical groups when the forecast covers only part of the trip.
- Historical rows labeled with their actual source dates and never described as forecasts.

### Budget section

- Group total range and typical total.
- Six category rows with minimum, typical, and maximum.
- Flight row explicitly labeled round-trip economy for the traveler count.
- A visible **Gemini estimate—not a live quote** label.

### Places section

- Up to 20 cards in Gemini relevance order.
- Name, short description, recommended days, and `best_for` tags.
- Select checkbox.
- **Open in Google Maps** external link.
- No per-place fabricated cost.

### Dashboard compatibility

- Replace the existing **Weather fit** score with API-sourced current condition and temperature text.
- Keep the typical total budget card backed by the persisted Gemini budget report.
- Do not display the deprecated trip or place weather-score fields anywhere.

### Refresh and failures

- Analysis starts only from an explicit button press.
- While running, the page shows that weather, budget, and places are being fetched.
- A failed refresh leaves the last successful report visible and adds a provider-specific retry message.
- Saving selected places remains independent of analysis refresh.

## Security and Privacy

- OpenWeather and Gemini keys remain in the backend environment file.
- Browser responses never contain provider keys.
- Gemini receives cities, dates, duration, traveler count, style, and currency only where required.
- Traveler names and email addresses never leave TripWise for planning analysis.
- HTTP exceptions are translated before they can expose query parameters or upstream bodies.
- Tests use fake HTTP transports. Automated tests never consume real provider quota.

## Testing

Backend tests cover:

- current weather parsing;
- five-day forecast aggregation;
- most-recent-period historical fallback, partial forecast coverage, year-boundary spans, and leap-day behavior;
- absence of deterministic weather fallback;
- budget prompt isolation and the 900-token ceiling;
- place prompt isolation, deduplication, bounds, and the 3,200-token ceiling;
- backend budget summation;
- absence of a calculated or exposed weather-fit score;
- preservation of the last successful report after each provider failure;
- atomic profile/place replacement;
- new-trip and legacy-trip departure-city behavior;
- safe provider error payloads;
- analysis reads that issue no provider calls.

Frontend tests cover:

- required departure city;
- detailed current and forecast weather;
- historical-weather labeling;
- flight-inclusive budget breakdown;
- provider source labels;
- place selection and encoded Google Maps links;
- refresh failure while retaining prior data;
- loading and empty states.

One manual end-to-end verification uses the configured providers with a synthetic trip, confirms a persisted report and map link, then deletes only that synthetic trip.

## Acceptance Criteria

- The Plan page contains no fixed destination catalog or fixed price estimate.
- One explicit analysis action makes exactly two Gemini requests.
- The budget request contains no place-discovery or prose task.
- The place request contains no budget, weather, or itinerary task.
- Weather is sourced only from OpenWeather/Open-Meteo.
- Trip dates outside the forecast horizon show the latest available matching historical data as historical, never as forecast.
- Total budget includes group flights and all five destination categories.
- At most 20 places are returned.
- Every place has a working keyless Google Maps search link.
- No weather-fit score or per-place fabricated cost is displayed.
- Invalid or failed provider responses never overwrite the last successful report.
- No secret is returned to or stored by the frontend.
