# TripTally

TripTally is a full-stack travel itinerary planner and shared-expense tracker. Create a trip, fetch API weather and Gemini budget guidance, choose relevant places with Google Maps links, generate a day-by-day itinerary, record equal or custom expenses, and finish with exact balances and a settlement plan.

Trip creation uses Photon/OpenStreetMap autocomplete to save canonical labels and coordinates. Planning analysis sends those coordinates to OpenWeather for current conditions and available forecasts; Open-Meteo supplies recent historical calendar dates when a trip is outside the forecast window. Two narrowly scoped Gemini requests estimate the complete group budget and suggest places. Results are validated and saved before the page changes. Itinerary and narrative generation can still use Gemini, a connected ChatGPT plan, an explicitly enabled OpenAI key, or the local provider.

## What is included

- Responsive React interface for dashboard, trip creation, planning, itinerary, expenses, people, and summary
- FastAPI REST API with PostgreSQL/SQLite persistence
- Exact `Decimal`-based expense splitting, idempotent writes, balances, and settlements
- Durable itinerary jobs with inline development execution or Redis/RQ workers
- Persisted provider-backed weather, budget, and place analysis with safe refreshes
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

Trip analysis requires an OpenWeather key and an enabled Gemini key. Add both to the Git-ignored `backend/.env` before choosing **Analyze trip**. Photon location search, Open-Meteo historical weather, and Google Maps search links do not require keys.

## Connect a ChatGPT plan

Start both local services, open [http://localhost:5173](http://localhost:5173), and choose **Continue with ChatGPT** in the top bar. During the Sign in with ChatGPT preview, eligible ChatGPT Plus and Pro accounts can authorize TripTally to use their plan for supported model inference.

Authorization returns to the loopback backend at `127.0.0.1`. Access, refresh, and ID tokens never enter browser storage: the backend writes them to the Git-ignored `backend/.tripwise/chatgpt-credentials.json` file with owner-only permissions. After connecting, open the **Using ChatGPT plan** control to choose a listable model, open ChatGPT usage settings, or disconnect. Disconnect revokes the renewable session before removing local tokens while retaining the non-secret host/client registration for a later sign-in.

Sign in with ChatGPT is separate from an OpenAI API key and API billing. TripTally prefers a connected ChatGPT plan, uses the legacy API-key route only when it is explicitly enabled, and otherwise keeps using the deterministic local provider. It never falls through from a failed ChatGPT-plan request to the API-key billing path.

## Use Gemini's free tier

Create a Gemini key in [Google AI Studio](https://aistudio.google.com/app/apikey), then set these values in the Git-ignored `backend/.env` file:

```env
TRIPWISE_GEMINI_ENABLED=true
TRIPWISE_GEMINI_API_KEY=your-key
TRIPWISE_GEMINI_MODEL=gemini-3.5-flash-lite
```

The key never enters the browser. Planning sends only the origin, destination, dates, duration, traveler count, travel style, and currency required for each request. Every successful analysis action makes one capped budget request and one capped place request; it does not send traveler names or email addresses. Google states that free-tier inputs may be used to improve its products.

## Demo workflow

1. Create a trip with a departure city, destination, dates, currency, budget, travel style, and travelers.
2. Choose **Analyze trip** to fetch current and trip-date weather, a flight-inclusive group budget, and ranked places. Normal page loads read the saved result and make no provider request.
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
| `TRIPWISE_WEATHER_PROVIDER` | `local` | Set `openweather` for planning analysis; the example file does this |
| `TRIPWISE_OPENWEATHER_API_KEY` | unset | Backend-only OpenWeather credential required for analysis |
| `TRIPWISE_OPENAI_ENABLED` | `false` | Explicit opt-in required before any OpenAI request |
| `TRIPWISE_OPENAI_API_KEY` | unset | Optional external AI provider credential |
| `TRIPWISE_OPENAI_MODEL` | `gpt-5-mini` | Optional AI model name |
| `TRIPWISE_GEMINI_ENABLED` | `false` | Explicit opt-in required before Gemini requests |
| `TRIPWISE_GEMINI_API_KEY` | unset | Backend-only Google AI Studio credential |
| `TRIPWISE_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Hosted free-tier model used for structured generation |
| `TRIPWISE_CHATGPT_CREDENTIALS_PATH` | `.tripwise/chatgpt-credentials.json` | Backend-only Sign in with ChatGPT session file |
| `TRIPWISE_CHATGPT_REDIRECT_URI` | `http://127.0.0.1:8000/api/v1/auth/chatgpt/callback` | Required loopback OAuth callback; do not replace `127.0.0.1` with `localhost` |
| `TRIPWISE_FRONTEND_URL` | `http://localhost:5173` | Browser destination after OAuth completes |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Browser API root, embedded at frontend build time |

When no hosted AI provider is enabled, TripTally can still use its local itinerary and prose provider. Expense tracking, balances, settlements, and previously saved data remain available. New planning analysis specifically requires Gemini and OpenWeather.

Trip creation saves the selected Photon label, country code, latitude, and longitude. Planning reads current conditions plus the available forecast from OpenWeather at those saved coordinates, avoiding ambiguous destination geocoding. Legacy trips without coordinates still use OpenWeather geocoding. Dates outside that forecast are mapped to the most recent matching historical period available from Open-Meteo and are labeled with their actual source dates. Weather API or payload failures return a safe retry error and leave the last saved analysis unchanged; there is no generated or local planning-weather fallback.

For planning, Gemini receives separate budget and place prompts whose JSON responses must match strict Pydantic schemas. The backend calculates budget totals, validates every response, and replaces the saved report and candidate places in one transaction. A failed refresh never partially overwrites a successful report. ChatGPT plan and OpenAI adapters remain available for itinerary and narrative generation; those provider errors enter the durable itinerary retry flow, while summary prose can use the local writer.

## Architecture

```text
React + TanStack Query
          |
          | REST /api/v1
          v
FastAPI routers -> domain services -> SQLAlchemy -> PostgreSQL / SQLite
                         |
                         +-> Photon / OpenStreetMap location search
                         +-> OpenWeather + Open-Meteo weather adapters
                         +-> isolated Gemini budget + place adapters
                         +-> local itinerary/prose adapters
                         +-> Sign in with ChatGPT token + model session
                         +-> durable Job -> inline handler or Redis/RQ worker
```

The monorepo is divided into:

- `frontend/`: React 19, TypeScript, Vite, Tailwind CSS, React Hook Form, Zod, and Vitest.
- `backend/app/api/`: thin HTTP routers and transport error mapping.
- `backend/app/services/`: trip, planning, itinerary, expense, settlement, and summary rules.
- `backend/app/providers/`: replaceable weather, currency, and AI boundaries.
- `backend/app/models/`: SQLAlchemy entities with portable UUIDs and numeric money columns.
- `backend/app/workers/`: queue selection and the shared itinerary job handler.
- `backend/tests/` and `frontend/tests/`: domain, lifecycle, and interaction tests.

All trip-scoped reads and writes verify the fixed demo user’s ownership. That boundary is preserved even though authentication is intentionally outside this release.

## AI and backend responsibility matrix

| Concern | Deterministic backend | AI/provider adapter |
| --- | --- | --- |
| Trip dates and day count | Owns and validates | Never calculates |
| Location identity | Requires a selected canonical option and persists coordinates | Photon/OpenStreetMap supplies filtered city, region, island, and country options |
| Weather facts | Validates, dates, labels, and persists API results | OpenWeather supplies current/forecast data at saved coordinates; Open-Meteo supplies historical rows; AI never participates |
| Budget bands and currency math | Validates currency/ranges and sums all six categories with `Decimal` | Gemini estimates category ranges, including round-trip group flights |
| Place ranking | Validates bounds and owns persisted selection rules | Gemini supplies up to 20 places in relevance order |
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
| `GET` | `/ai/status` | Read the safe active-provider status |
| `GET` | `/auth/chatgpt/start` | Start loopback Sign in with ChatGPT authorization |
| `GET` | `/auth/chatgpt/callback` | Validate the OAuth callback and return to the frontend |
| `GET` | `/auth/chatgpt/status` | Read safe account, plan, and selected-model status |
| `POST` | `/auth/chatgpt/model` | Select a model available to the connected plan |
| `POST` | `/auth/chatgpt/disconnect` | Revoke and clear the ChatGPT session |
| `GET` | `/locations/search` | Search filtered Photon location options for trip creation |
| `GET`, `POST` | `/trips` | List or create trips |
| `GET`, `DELETE` | `/trips/{trip_id}` | Read or delete a trip |
| `POST`, `DELETE` | `/trips/{trip_id}/archive` | Archive or restore a trip |
| `GET`, `POST` | `/trips/{trip_id}/travelers` | List or add travelers |
| `DELETE` | `/trips/{trip_id}/travelers/{traveler_id}` | Remove an unused traveler |
| `POST` | `/trips/{trip_id}/analyze` | Run weather, budget, and place analysis |
| `GET` | `/trips/{trip_id}/analysis` | Read the last successful analysis without contacting providers |
| `GET` | `/trips/{trip_id}/places` | List candidate places |
| `POST` | `/trips/{trip_id}/places/select` | Save place selection |
| `POST`, `GET` | `/trips/{trip_id}/itinerary/generate`, `/trips/{trip_id}/itinerary` | Generate or read itinerary |
| `GET`, `POST` | `/trips/{trip_id}/expenses` | Filter/list or create expenses |
| `DELETE` | `/trips/{trip_id}/expenses/{expense_id}` | Delete an expense |
| `GET` | `/trips/{trip_id}/balances` | Calculate traveler balances |
| `GET` | `/trips/{trip_id}/settlements` | Calculate transfers |
| `GET` | `/trips/{trip_id}/summary` | Build the final trip summary |
| `GET` | `/jobs/{job_id}` | Read durable job state |

Invalid requests return `422`, missing or inaccessible resources return `404`, and conflicting idempotency keys return `409`. Planning provider failures return `502` with a fixed code such as `{ "detail": { "code": "weather_unavailable" } }`; credentials and upstream response details are never returned.

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

This release does not include TripTally user accounts, booking, live multi-user collaboration, a maps UI, receipt OCR, or production payment flows. Sign in with ChatGPT authorizes only the AI provider and does not replace the fixed TripTally demo user. The fixed demo user and provider interfaces keep the domain ready for application authentication later without presenting incomplete security or booking features as production-ready behavior.
