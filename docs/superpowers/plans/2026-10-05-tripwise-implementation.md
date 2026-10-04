# TripWise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, runnable AI-assisted travel itinerary and group expense application.

**Architecture:** A React/TypeScript single-page application consumes a FastAPI REST API backed by SQLAlchemy/PostgreSQL. External weather, currency, place, and AI behavior is adapter-based with deterministic local fallbacks; itinerary work shares a durable job handler between Redis workers and inline development execution.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Hook Form, Zod, FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL 16, Redis 7, RQ, pytest, Vitest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-05-tripwise-design.md`

## Global Constraints

- All generated files stay under `/Users/shreyaanand/Desktop/Go-pract/Projects/TripWise`.
- Store and calculate money with `Decimal`/`NUMERIC`, rounded half-up to two places.
- AI never calculates weather data, budgets, splits, balances, settlements, or numeric summaries.
- Trip-scoped operations verify demo-user ownership and cross-trip child IDs.
- Expense creation and explicit split storage are one database transaction.
- Totals are aggregated from expense rows and never maintained as mutable counters.
- The application remains usable without external API keys or a running Redis service.

## Review Focus

- Equal splits whose base amount contains remainder cents must sum exactly to the expense.
- Custom splits with duplicate, omitted, foreign-trip, negative, or mismatched shares must fail atomically.
- Reused idempotency keys return the prior record only for an identical canonical request.
- Provider and worker failures must leave the trip readable and the job retryable or terminal after three attempts.
- Empty/loading/error states and mobile layouts must keep every primary workflow reachable.

---

### Task 1: Backend foundation and domain model

**Files:** Create `backend/pyproject.toml`, `backend/app/core/*`, `backend/app/db/*`, `backend/app/models/*`, `backend/tests/conftest.py`, and migration/bootstrap support.

**Interfaces:** Produce `Settings`, `Base`, `get_db()`, `init_db()`, enums, and all SQLAlchemy entities consumed by later services.

- [ ] Write model/validation tests for trip dates, portable UUIDs, relationships, cascades, and decimal columns.
- [ ] Run the focused tests and confirm they fail because the application modules do not exist.
- [ ] Implement settings, engine/session factories, enums, timestamps, entities, indexes, foreign keys, and demo-user initialization.
- [ ] Run the focused tests and confirm they pass on SQLite.

### Task 2: Trip, traveler, analysis, and place services

**Files:** Create `backend/app/schemas/trip.py`, `backend/app/schemas/place.py`, providers, `trip_service.py`, `planning_service.py`, and associated tests.

**Interfaces:** Produce trip CRUD, traveler CRUD, `analyze_trip(db, trip)`, `list_places`, and `select_places`.

- [ ] Write failing tests for derived end dates, invalid values, authorization, deterministic analysis, scoring bounds, and foreign place selection.
- [ ] Implement schemas and deterministic provider adapters with concurrent analysis orchestration.
- [ ] Run the service tests and verify all assertions pass.

### Task 3: Expense transactions, idempotency, balances, and settlements

**Files:** Create expense schemas/services and `backend/tests/test_expenses.py`, `test_settlements.py`.

**Interfaces:** Produce `create_expense`, `list_expenses`, `delete_expense`, `calculate_balances`, and `calculate_settlements`.

- [ ] Write failing tests for exact equal remainders, valid custom splits, every invalid share class, cross-trip payer, rollback, filters, idempotency replay/conflict, balance conservation, and deterministic settlement transfers.
- [ ] Implement canonical request hashing, currency conversion, atomic expense/split persistence, aggregate queries, and greedy settlement matching.
- [ ] Run expense and settlement tests and confirm they pass.

### Task 4: Itinerary jobs and final summaries

**Files:** Create itinerary/AI schemas, providers, services, worker queue/handlers, and tests.

**Interfaces:** Produce `enqueue_itinerary`, `run_itinerary_job(job_id)`, `get_itinerary`, `build_summary`, and `get_job`.

- [ ] Write failing tests for selected-place requirements, structured validation, exact day count, replacement atomicity, retries/dead jobs, category summaries, and AI fallback prose.
- [ ] Implement deterministic structured itinerary generation, OpenAI adapter boundary, durable jobs, Redis/inline dispatch, and backend-owned numeric summary creation.
- [ ] Run the focused tests and verify they pass.

### Task 5: FastAPI surface and lifecycle integration

**Files:** Create routers under `backend/app/api`, `backend/app/main.py`, and `backend/tests/test_api.py`.

**Interfaces:** Expose the versioned endpoints and `{detail}` error contract from the design spec.

- [ ] Write a failing integration test that creates a trip/travelers, analyzes, selects places, generates itinerary, records expenses, and obtains balances/settlements/summary.
- [ ] Implement dependency injection, exception mapping, CORS, request IDs, routers, and health endpoint.
- [ ] Run the entire backend suite and confirm lifecycle and authorization tests pass.

### Task 6: Frontend foundation and application shell

**Files:** Create frontend Vite/Tailwind config, typed API client, query hooks, routing, design tokens, shared layout/components, and tests.

**Interfaces:** Produce `api`, query-key factory, `AppRouter`, `TripLayout`, and reusable status/form/display primitives.

- [ ] Write failing tests for API error normalization, route rendering, and mobile navigation behavior.
- [ ] Implement the frontend foundation and distinctive responsive visual system.
- [ ] Run Vitest, TypeScript, and ESLint and resolve all failures.

### Task 7: Trip creation, dashboard, overview, planning, and itinerary flows

**Files:** Create page/features for dashboard, create trip, overview, plan, and itinerary plus tests.

**Interfaces:** Pages consume typed query/mutation hooks and invalidate stable trip keys after changes.

- [ ] Write failing interaction tests for creating a trip with travelers, running analysis, selecting places, launching a job, and displaying an itinerary.
- [ ] Implement empty/loading/error/populated states and responsive cards/timeline.
- [ ] Run focused UI tests and the production type check.

### Task 8: Expense, people, and summary flows

**Files:** Create expense form/list/category display, people balances, summary/settlement views, and tests.

**Interfaces:** Expense form emits the exact backend equal/custom payload and a per-submission idempotency key.

- [ ] Write failing tests for equal/custom form switching, share total feedback, participant selection, balance rendering, settlement rendering, and currency formatting.
- [ ] Implement mutations, filters, modal/sheet behavior, charts without a heavy chart dependency, and accessible feedback.
- [ ] Run all frontend checks and production build.

### Task 9: Operations, demo data, and documentation

**Files:** Create Dockerfiles, `docker-compose.yml`, `.env.example`, root scripts, seed command, README, and ignore files.

**Interfaces:** Provide `make dev`, `make test`, `make seed`, and `docker compose up --build` workflows.

- [ ] Add a seed test verifying the demo is idempotent and produces a complete trip.
- [ ] Implement containers, health checks, environment documentation, responsibility matrix, setup, demo, API, test, and architecture sections.
- [ ] Validate Compose configuration and execute the seed command twice.

### Task 10: Whole-project verification and review

**Files:** Modify only files implicated by verification failures.

- [ ] Run backend formatting/static checks and full pytest suite.
- [ ] Run frontend ESLint, Vitest, TypeScript, and production build.
- [ ] Validate Docker Compose and smoke-test backend health plus frontend serving when the local Docker daemon is available.
- [ ] Review the implementation against every design-spec section, fix gaps, and record exact verification results in the handoff.
