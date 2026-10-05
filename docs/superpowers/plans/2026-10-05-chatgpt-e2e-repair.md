# ChatGPT End-to-End Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TripWise's Sign in with ChatGPT flow diagnosable and compatible with the current official OAuth and Responses contracts from authorization through first inference.

**Architecture:** Keep OAuth secrets backend-only while classifying failures at safe stage boundaries. Reuse the stored issued client for returning callbacks, persist validated credentials before model discovery, and send prompt instructions through the supported Responses `instructions` field. A fake-upstream integration test will exercise the whole local flow without real credentials.

**Tech Stack:** FastAPI, httpx, Pydantic, OpenAI Python SDK, React, TypeScript, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-05-chatgpt-sign-in-design.md`

## Global Constraints

- Change files only inside `/Users/shreyaanand/Desktop/Go-pract/Projects/TripWise`.
- Never read, print, log, or expose API keys, OAuth tokens, authorization codes, state, nonce, or PKCE verifier values.
- Automated tests use local fakes only and never contact OpenAI.
- Keep the development frontend and backend on ports `5173` and `8000`.
- Do not use workplace services.

## Review Focus

- Returning callbacks may omit `client_id`; the stored issued ID must be reused while mismatches are rejected.
- Each OAuth failure boundary must redirect with a fixed safe reason and no upstream text.
- A model-catalog failure after valid identity must retain the verified registration and tokens.
- ChatGPT-plan inference must use `instructions`, never an explicit `system` message.
- The fake end-to-end test must cover start, callback, token exchange, identity validation, model discovery, safe persistence/status, and streamed completion.

---

### Task 1: OAuth completion compatibility and safe diagnostics

**Files:**
- Modify: `backend/app/chatgpt/service.py`
- Modify: `backend/app/api/chatgpt.py`
- Modify: `backend/tests/test_chatgpt_auth.py`
- Modify: `backend/tests/test_chatgpt_api.py`

**Interfaces:**
- Produces: `ChatGPTAuthorizationError(reason)` with one fixed safe callback reason.
- Consumes: stored `ChatGPTCredentials.client_id`, callback `client_id`, and existing safe frontend redirect helper.

- [ ] Write failing tests proving a returning callback without `client_id` succeeds, a mismatched returned ID fails, model-discovery failure retains validated credentials, and each stage maps to a fixed reason.
- [ ] Run the focused backend tests and confirm the failures are caused by the current callback rules and generic catch.
- [ ] Implement stored-client reuse, returning-subject validation, pre-catalog credential persistence, and stage-specific exception wrapping.
- [ ] Run the focused backend tests to green.
- [ ] Commit the task.

### Task 2: Supported first-inference request shape

**Files:**
- Modify: `backend/app/providers/ai.py`
- Modify: `backend/tests/test_itinerary_summary.py`

**Interfaces:**
- Produces: `_stream_parsed(..., instructions, input_messages, ...)` using `responses.stream`, `store=False`, and user/developer input only.
- Consumes: generated itinerary/summary instructions and structured-output schemas.

- [ ] Write failing tests that reject explicit `system` input and require `instructions` plus `store=False`.
- [ ] Run the focused tests and confirm they fail on the current request body.
- [ ] Move system guidance into `instructions` and leave complete request facts in the `input` array.
- [ ] Run the focused backend tests to green.
- [ ] Commit the task.

### Task 3: Fake full-flow regression and actionable frontend errors

**Files:**
- Create: `backend/tests/test_chatgpt_e2e.py`
- Modify: `frontend/src/components/ChatGPTConnection.tsx`
- Modify: `frontend/tests/chatgpt-connection.test.tsx`

**Interfaces:**
- Produces: one fake-upstream integration path from `/start` through protected status and streamed first inference; safe human-readable copy for every callback reason.
- Consumes: the Task 1 failure reasons and Task 2 request shape.

- [ ] Write failing backend and frontend tests for the complete fake flow and stage-specific user messages.
- [ ] Run both focused suites and confirm failures reflect missing orchestration/copy.
- [ ] Add the minimal fake full-flow fixture and safe frontend message mapping.
- [ ] Run both focused suites to green.
- [ ] Run all backend and frontend verification gates, inspect the live UI, and commit the task.

