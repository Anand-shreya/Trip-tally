# TripWise

TripWise is a full-stack travel itinerary planner and shared-expense tracker. Create a trip, get deterministic weather and budget guidance, choose recommended places, generate a day-by-day itinerary, record equal or custom expenses, and finish with exact balances and a settlement plan.

The application is deliberately useful without paid services: its default weather, destination, currency, itinerary, and narrative providers are local and deterministic. An OpenAI key is optional.

## What is included

- Responsive React interface for dashboard, trip creation, planning, itinerary, expenses, people, and summary
- FastAPI REST API with PostgreSQL/SQLite persistence
- Exact `Decimal`-based expense splitting, idempotent writes, balances, and settlements
- Durable itinerary jobs with inline development execution or Redis/RQ workers
- Deterministic demo data and provider fallbacks
- Docker Compose stack with PostgreSQL, Redis, API, worker, and Nginx-served frontend
- Backend and frontend automated test suites

## Quick start with Docker

Prerequisites: Docker with the Compose plugin and Make.

```bash
cp .env.example .env
make dev
```

Open [http://localhost:5173](http://localhost:5173). The API health endpoint is [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health), and interactive API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

In another terminal, load the showcase trip once the services are healthy:

```bash
make seed-docker
```

The seed is idempotent, so running it again returns the same trip instead of duplicating it. Stop the stack with `make down`. PostgreSQL data remains in the named Docker volume.

## Direct local development

Prerequisites: Python 3.11 or newer and Node.js 22 or newer.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
make install
cp .env.example backend/.env
```

The default configuration uses SQLite and inline background jobs, so PostgreSQL and Redis are not required. Start each process in its own terminal:

```bash
make backend
make frontend
```

Optionally create the complete Kerala showcase trip:

```bash
make seed
```

The backend stores the direct-development SQLite database at `backend/tripwise.db`.

## Demo workflow

1. Create a trip with destination, dates, currency, budget, travel style, and travelers.
2. Run analysis to see seasonal conditions, a budget range, and ranked destination cards.
3. Select places and generate the itinerary.
4. Add group expenses using equal or custom shares. Every submission carries an idempotency key.
5. Review each traveler’s net balance and the deterministic settlement instructions.
6. Open the summary for total spend, remaining budget, category distribution, and narrative highlights.

The seeded demo has already completed every step and includes three travelers, selected places, a five-day itinerary, and expenses across accommodation, food, and transport.

## Configuration

Backend settings use the `TRIPWISE_` prefix. For direct development, copy `.env.example` to
`backend/.env`; Docker Compose reads the root `.env`. Never commit real secrets.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TRIPWISE_DATABASE_URL` | `sqlite+pysqlite:///./tripwise.db` | SQLAlchemy database URL |
| `TRIPWISE_REDIS_URL` | `redis://localhost:6379/0` | Redis connection used by RQ |
| `TRIPWISE_QUEUE_MODE` | `inline` | `inline` executes jobs immediately; `redis` queues them |
| `TRIPWISE_CORS_ORIGINS` | `["http://localhost:5173"]` | JSON array of allowed browser origins |
| `TRIPWISE_WEATHER_PROVIDER` | `local` | Use `openweather` for live current conditions |
| `TRIPWISE_OPENWEATHER_API_KEY` | unset | Personal OpenWeather credential |
| `TRIPWISE_OPENAI_ENABLED` | `false` | Explicit opt-in required before any OpenAI request |
| `TRIPWISE_OPENAI_API_KEY` | unset | Optional external AI provider credential |
| `TRIPWISE_OPENAI_MODEL` | `gpt-5-mini` | Optional AI model name |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Browser API root, embedded at frontend build time |

When `TRIPWISE_OPENAI_API_KEY` is absent, TripWise uses its deterministic itinerary and prose provider. The core product remains fully functional.

When `TRIPWISE_WEATHER_PROVIDER=openweather` and a key is configured, analysis uses live current
conditions from OpenWeather. These conditions are labeled as current observations rather than a
future forecast. API or payload failures automatically fall back to the deterministic local provider.

Only when `TRIPWISE_OPENAI_ENABLED=true` and a key is configured does itinerary generation use the
OpenAI Responses API with a Pydantic schema, following the official
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
Provider errors enter the durable itinerary retry flow; summary prose falls back to the deterministic
local writer.

## Architecture

```text
React + TanStack Query
          |
          | REST /api/v1
          v
FastAPI routers -> domain services -> SQLAlchemy -> PostgreSQL / SQLite
                         |
                         +-> deterministic provider adapters
                         +-> durable Job -> inline handler or Redis/RQ worker
```

The monorepo is divided into:

- `frontend/`: React 19, TypeScript, Vite, Tailwind CSS, React Hook Form, Zod, and Vitest.
- `backend/app/api/`: thin HTTP routers and transport error mapping.
- `backend/app/services/`: trip, planning, itinerary, expense, settlement, and summary rules.
- `backend/app/providers/`: replaceable weather, currency, place catalog, and AI boundaries.
- `backend/app/models/`: SQLAlchemy entities with portable UUIDs and numeric money columns.
- `backend/app/workers/`: queue selection and the shared itinerary job handler.
- `backend/tests/` and `frontend/tests/`: domain, lifecycle, and interaction tests.

All trip-scoped reads and writes verify the fixed demo user’s ownership. That boundary is preserved even though authentication is intentionally outside this release.

## AI and backend responsibility matrix

| Concern | Deterministic backend | AI/provider adapter |
| --- | --- | --- |
| Trip dates and day count | Owns and validates | Never calculates |
| Weather score and seasonal facts | Owns numeric result through weather adapter | May supply replaceable raw/provider data |
| Budget bands and currency math | Owns with `Decimal` | Never calculates |
| Place ranking | Owns bounded score and selection rules | May provide catalog descriptions |
| Itinerary structure | Validates exact dates, day count, and activity times | May propose structured activities and prose |
| Expense shares and idempotency | Owns transactionally | Never participates |
| Balances, category totals, settlements | Owns from persisted expense rows | Never calculates |
| Summary narrative | Supplies verified numeric facts | May turn those facts into prose; local fallback is always available |

AI output cannot overwrite accounting results. A generated itinerary is persisted only after its complete structured payload passes backend validation.

## REST API

All application routes are rooted at `/api/v1`.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API health |
| `GET`, `POST` | `/trips` | List or create trips |
| `GET`, `DELETE` | `/trips/{trip_id}` | Read or delete a trip |
| `POST`, `DELETE` | `/trips/{trip_id}/archive` | Archive or restore a trip |
| `GET`, `POST` | `/trips/{trip_id}/travelers` | List or add travelers |
| `DELETE` | `/trips/{trip_id}/travelers/{traveler_id}` | Remove an unused traveler |
| `POST` | `/trips/{trip_id}/analyze` | Run weather, budget, and place analysis |
| `GET` | `/trips/{trip_id}/places` | List candidate places |
| `POST` | `/trips/{trip_id}/places/select` | Save place selection |
| `POST`, `GET` | `/trips/{trip_id}/itinerary/generate`, `/trips/{trip_id}/itinerary` | Generate or read itinerary |
| `GET`, `POST` | `/trips/{trip_id}/expenses` | Filter/list or create expenses |
| `DELETE` | `/trips/{trip_id}/expenses/{expense_id}` | Delete an expense |
| `GET` | `/trips/{trip_id}/balances` | Calculate traveler balances |
| `GET` | `/trips/{trip_id}/settlements` | Calculate transfers |
| `GET` | `/trips/{trip_id}/summary` | Build the final trip summary |
| `GET` | `/jobs/{job_id}` | Read durable job state |

Invalid requests return `422`, missing or inaccessible resources return `404`, and conflicting idempotency keys return `409`. Application errors consistently use `{ "detail": "..." }`.

## Expense guarantees

Money is stored as `NUMERIC`/`Decimal` and rounded half-up to two places. Equal-split remainder cents are assigned in stable traveler order, so stored shares always equal the base amount. Custom splits must contain one non-negative share for each included traveler and must total the converted base amount exactly.

Creating an expense and all of its explicit split rows is one transaction. The `Idempotency-Key` is unique per trip: an identical replay returns the original record, while a different payload with that key is rejected.

Balances are computed as `paid - owed`. Settlement generation deterministically matches debtors and creditors until every rounded balance reaches zero.

## Tests and quality checks

Run the normal project checks with:

```bash
make test
```

For the complete release gate:

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/pytest backend/tests
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run build
docker compose config --quiet
```

Backend tests run against in-memory SQLite through the same SQLAlchemy/service boundaries used by PostgreSQL. Frontend tests exercise the real forms and route components while substituting only the HTTP boundary.

## Deliberate MVP boundaries

This release does not include login/accounts, booking, live multi-user collaboration, a maps UI, receipt OCR, or production payment flows. The fixed demo user and provider interfaces keep the domain ready for those additions without presenting incomplete security or booking features as production-ready behavior.
