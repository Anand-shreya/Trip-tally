# TripWise Design

## Purpose

TripWise is an AI-assisted trip planner and group expense tracker. A user creates a trip, checks seasonal weather suitability and estimated cost, chooses recommended places, generates a day-by-day itinerary, records shared expenses, and receives exact balances and a deterministic settlement plan.

The first release is a polished single-user portfolio application. It deliberately excludes authentication, booking, live collaboration, maps UI, and receipt OCR. A fixed demo user owns every trip, while every trip-scoped API still performs ownership checks so authentication can be introduced later without changing the domain boundary.

## Success Criteria

- A new visitor can create and revisit trips from the dashboard.
- A trip can contain travelers, analysis, selected places, and an itinerary.
- Weather, cost, and place analysis works without paid API keys by using deterministic local providers; configured external providers can replace those adapters.
- Equal and custom expenses are stored transactionally with explicit per-traveler shares.
- Duplicate expense submissions with the same idempotency key return the original expense.
- Balances, category totals, final summary, and settlements are calculated from persisted expenses rather than mutable counters or AI output.
- AI enhances descriptions, itineraries, and prose only. Backend code owns dates, money, weather scoring, expense math, and settlement math.
- The full stack runs with Docker Compose and the backend/frontend can also run directly for development.

## Architecture

The repository is a monorepo with `backend` and `frontend` applications. The React client calls a versioned REST API. FastAPI routes delegate to focused services, Pydantic validates transport data, and SQLAlchemy persists the domain model in PostgreSQL. Tests use SQLite through the same repository and service interfaces.

Itinerary generation creates a durable job record. When Redis is available the job is queued for an RQ worker; when it is not, the API runs the same job handler immediately. This preserves a runnable local experience without weakening the queue design. Jobs use `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `RETRY`, and `DEAD` states with a maximum of three attempts.

External behavior is behind adapters:

- Weather: deterministic seasonal estimates by default, Open-Meteo when enabled.
- Currency: same-currency conversion and configured reference rates by default, live HTTP provider when enabled.
- Places/maps: curated destination catalog with coordinates and travel-time estimates.
- AI: deterministic structured itinerary and summary by default, OpenAI Responses API structured output when `OPENAI_API_KEY` is present.

Provider failures never delete or invalidate a trip. The API returns usable deterministic results and stores a recoverable job failure where appropriate.

## Backend Components

- `core`: settings, enums, typed application errors, demo-user identity.
- `db`: engine/session lifecycle, declarative base, database initialization.
- `models`: user, trip, traveler, place, itinerary day/activity, expense/split, idempotency metadata, and job.
- `schemas`: strict request and response contracts with decimal-safe money fields.
- `services`: authorization, trip CRUD, analysis, place selection, itinerary generation, expense transactions, balances/settlements, and summaries.
- `providers`: weather, currency, catalog/maps, and AI adapters.
- `api`: thin routers for trips, travelers, planning, places, itineraries, expenses, summaries, and jobs.
- `workers`: Redis queue adapter and shared job handlers.

## Data and Money Rules

UUID primary keys are represented as strings at the API boundary. PostgreSQL uses native UUID-compatible values through SQLAlchemy's portable UUID type. Money uses `Decimal` and `NUMERIC`, never binary floats. Values are rounded half-up to two decimal places.

An expense stores original amount/currency, exchange rate, base amount, payer, date, category, and notes. Each split stores the actual base-currency share. Equal split remainder cents are assigned in stable traveler order so shares always sum exactly to the base amount. Custom shares must be non-negative, reference distinct included travelers, and equal the base amount.

Expense and split inserts happen in one transaction. An idempotency key is unique within a trip. Reuse with the same canonical request returns the existing expense; reuse with a different request returns `409 Conflict`.

Balances use `paid - owed`. Positive travelers are creditors and negative travelers are debtors. The settlement service sorts both groups by amount then traveler ID, greedily matches them, and emits transfers until all rounded balances reach zero.

## Planning Rules

Trip end date is derived from start date plus `number_of_days - 1`. Analysis concurrently obtains weather, currency context, and candidate places. The cost engine returns minimum, typical, and maximum totals from daily per-traveler bands adjusted by travel style and trip length. Recommended places receive scores from weather, duration fit, budget fit, interests, and travel efficiency.

Selected places must belong to the trip. At least one place is required for itinerary generation. A structured itinerary must contain exactly the trip's number of days; each day number/date is valid; and every activity has `start_time < end_time`. Existing itinerary rows are replaced in a transaction only after the new structured result validates.

## API

The API is rooted at `/api/v1` and includes:

- `GET /health`
- `GET|POST /trips`, `GET|DELETE /trips/{trip_id}`
- `GET|POST /trips/{trip_id}/travelers`, `DELETE /trips/{trip_id}/travelers/{traveler_id}`
- `POST /trips/{trip_id}/analyze`
- `GET /trips/{trip_id}/places`, `POST /trips/{trip_id}/places/select`
- `POST /trips/{trip_id}/itinerary/generate`, `GET /trips/{trip_id}/itinerary`
- `GET|POST /trips/{trip_id}/expenses`, `DELETE /trips/{trip_id}/expenses/{expense_id}`
- `GET /trips/{trip_id}/balances`, `/settlements`, and `/summary`
- `GET /jobs/{job_id}`

Invalid input is `422`, missing resources are `404`, ownership violations are intentionally surfaced as `404`, and idempotency conflicts are `409`. Error responses use `{ "detail": "..." }`.

## Frontend

The interface uses a warm editorial travel aesthetic: deep ink text, sand surfaces, terracotta accents, restrained teal status colors, and serif display headings paired with a readable sans-serif UI font. It is responsive from mobile to desktop and does not rely on stock dashboard styling.

Routes:

- `/`: trip dashboard with empty, loading, error, and populated states.
- `/trips/new`: trip and traveler creation wizard.
- `/trips/:id`: overview.
- `/trips/:id/plan`: weather, budget range, and selectable place cards.
- `/trips/:id/itinerary`: generation status and day timeline.
- `/trips/:id/expenses`: totals, filters, list, equal/custom expense form.
- `/trips/:id/people`: traveler management and balance cards.
- `/trips/:id/summary`: budget outcome, category breakdown, settlement instructions, and narrative summary.

TanStack Query owns server state and invalidation. React Hook Form plus Zod owns client validation. A typed fetch client normalizes backend errors. Currency formatting uses the trip's base currency and the browser's `Intl.NumberFormat`.

## Testing

Backend unit tests cover weather/cost scoring, exact equal-split cents, custom split rejection, cross-trip IDs, idempotency reuse/conflict, filtering, balance conservation, settlement output, and summary aggregation. API integration tests cover the full trip lifecycle and job behavior.

Frontend tests cover the typed client, creation form, place selection, equal/custom expense form validation, itinerary states, navigation, and summary rendering. The release check runs backend pytest, frontend Vitest, TypeScript compilation, ESLint, and production build. A Docker Compose config validation is included when Docker is available.

## Operations and Security

Secrets are read only from environment variables and `.env` is ignored. CORS origins are configurable. Logs include request/job identifiers but no secrets. Database health and API health are separate checks in Docker Compose. Containers run application processes without modifying the host outside this repository.

The README explicitly documents the AI/backend responsibility split, direct and Docker setup, environment variables, demo workflow, API docs, tests, and deliberate MVP boundaries.
