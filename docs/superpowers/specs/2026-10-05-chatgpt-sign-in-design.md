# TripWise Sign in with ChatGPT Design

## Purpose

TripWise will let its local user connect an eligible ChatGPT account and use that account's ChatGPT plan for itinerary and summary generation. The connection replaces manual API-key setup as the primary AI path while preserving the deterministic local provider when no ChatGPT plan is connected.

This is a personal, loopback-only integration. It does not turn the fixed TripWise demo user into a general authentication system, does not send trip or credential data to any workplace service, and never exposes OpenAI credentials to the browser.

## Success Criteria

- The top bar shows the required `Continue with ChatGPT` action when no account is connected.
- Authorization uses OpenAI's dynamic-client OAuth flow with PKCE S256, state, nonce, the required scopes and resource, and a `127.0.0.1` loopback callback.
- The backend verifies the ID token before accepting an account and stores access and refresh tokens only in a project-local file with mode `0600`.
- The UI can show the connected account, available model, selected model, ChatGPT-plan status, a usage-management link, and a disconnect action without receiving tokens or dynamic client identifiers.
- Connected ChatGPT credentials take priority over the explicitly enabled legacy API-key provider; neither path runs without an intentional connection or opt-in.
- ChatGPT-plan inference uses streaming Responses API requests with `store=false`, complete request history, schema-validated output, and completion only after `response.completed`.
- Access tokens refresh shortly before expiry, refreshes are serialized, and disconnect revokes the refresh token before clearing local credentials.
- A declined token-sharing scope retains the verified registration and account identity but clearly reports that ChatGPT-plan usage is unavailable.
- All OAuth, JWKS, model, token, refresh, revocation, and inference tests use local fakes. Automated tests never open a real sign-in flow or use the stored API key.
- The existing local provider, trip data, OpenWeather integration, expense math, archive/delete flows, and live development site remain intact.

## Official Protocol Baseline

The implementation follows the official OpenAI Sign in with ChatGPT documentation:

- [Quickstart](https://developers.openai.com/siwc/quickstart)
- [Sign-in flow](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Profiles and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [UI/UX guidelines](https://developers.openai.com/siwc/ui-ux-guidelines)

Protocol constants are:

- Authorization endpoint: `https://auth.openai.com/api/accounts/authorize`
- Token endpoint: `https://auth.openai.com/api/accounts/oauth/token`
- Revocation endpoint: `https://auth.openai.com/api/accounts/oauth/revoke`
- JWKS endpoint: `https://auth.openai.com/.well-known/jwks.json`
- Resource: `https://api.openai.com/v1`
- Initial client identifier: `dynamic_agent_client`
- Scopes: `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`
- Issuer: `https://auth.openai.com`

## Architecture

The backend owns the complete OAuth and inference lifecycle. A focused `app/chatgpt` package contains credential persistence, single-use authorization transactions, ID-token verification, token exchange and refresh, model discovery, and disconnect behavior. A thin FastAPI router exposes safe browser operations under `/api/v1/auth/chatgpt`.

The React top bar renders a compact connection control. Starting authorization is a full-page navigation to the backend on `http://127.0.0.1:8000`; this ensures the state cookie and callback share the required loopback host. After the backend completes the callback, it redirects to `http://localhost:5173/?chatgpt=connected` or a safe error indicator. Routine status and mutation requests continue through the existing frontend API base.

The AI adapter asks the ChatGPT service for a valid access token and selected model before considering the legacy API-key path. It constructs the official OpenAI SDK client only on demand. Accounting, budget, weather, ranking, and persisted date validation remain backend-owned.

## Credential Storage

Credentials live at `backend/.tripwise/chatgpt-credentials.json` by default. `.tripwise/` is ignored by Git. The configured path may be absolute for tests, but the product default remains inside this project.

The store uses atomic replacement and enforces mode `0600` on both temporary and final files. The JSON document contains:

- Stable opaque host ID in `urn:uuid:<uuid>` form.
- Issued dynamic client ID; `dynamic_agent_client` is never persisted as an issued ID.
- Verified subject, email, and display name.
- ID, access, and refresh tokens.
- Granted scopes and access-token expiry in UTC.
- Listable model slugs and the selected model.

Disconnect clears tokens, account identity, scopes, model availability, and selection only after revocation succeeds. It retains the stable host ID and issued client ID so a later authorization is a returning sign-in rather than a new host registration.

## Authorization Flow

### Start

`GET /api/v1/auth/chatgpt/start` generates cryptographically random state, nonce, and PKCE verifier values. The verifier is converted to an S256 challenge. A process-local transaction store retains the exact redirect URI and values for ten minutes.

The response sets the state in an HttpOnly, SameSite=Lax, ten-minute cookie and redirects to the authorization endpoint. Initial registration sends `dynamic_agent_client`, `agent_name_hint=TripWise`, and the stable host ID. Returning authorization sends the issued client ID and omits the agent-name hint.

### Callback

`GET /api/v1/auth/chatgpt/callback` rejects OAuth errors, missing values, cookie/query state mismatches, expired transactions, and replayed transactions. It consumes a valid transaction exactly once.

For initial registration, the callback's issued `client_id` is required and must not equal `dynamic_agent_client`. Returning authorization must use the stored issued client ID. The backend exchanges the code using the exact redirect URI and PKCE verifier, verifies the ID token's signature, issuer, audience, expiry, nonce, and non-empty subject, then fetches models using the access token.

Only model records with `visibility == "list"` are exposed. If the required direct-token scope is absent, the backend still saves the verified identity and issued registration but sets plan access to disabled. The callback clears the state cookie and redirects to the frontend with only a success or safe error code.

### Refresh and Disconnect

The service refreshes an access token when less than two minutes remain. A lock serializes refreshes, and the service reloads credentials after acquiring it so concurrent callers reuse the first refreshed token. Refresh-token rotation is persisted when the endpoint supplies a new refresh token.

Disconnect posts the refresh token and issued client ID to the revocation endpoint. A failed revocation leaves the local credentials available for a retry and returns an actionable error; a successful revocation removes the sensitive session values.

## Backend HTTP Contract

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/api/v1/auth/chatgpt/start` | Set one-time state cookie and redirect to OpenAI |
| `GET` | `/api/v1/auth/chatgpt/callback` | Validate, exchange, verify, discover models, persist, and redirect |
| `GET` | `/api/v1/auth/chatgpt/status` | Return safe account, plan, and model status only |
| `POST` | `/api/v1/auth/chatgpt/model` | Select a slug from the current listable models |
| `POST` | `/api/v1/auth/chatgpt/disconnect` | Revoke and clear the local ChatGPT session |

The status response contains `signed_in`, `plan_enabled`, `name`, masked-safe email, `models`, `selected_model`, and `manage_usage_url`. It never contains tokens, the issued client ID, host ID, nonce, verifier, or state.

## Inference

Provider priority is:

1. A verified ChatGPT session with the direct-token scope and selected listable model.
2. The legacy API-key provider only when `TRIPWISE_OPENAI_ENABLED=true` and a key is configured.
3. The deterministic local provider.

TripWise never silently switches a ChatGPT-plan error to the legacy billed API-key path. Each structured OpenAI request uses `responses.stream`, `store=False`, the complete system and user messages, and a Pydantic `text_format`. The adapter consumes the stream and accepts a result only after seeing `response.completed` and a non-null parsed object.

Itinerary failures continue through the existing three-attempt durable-job lifecycle. Summary failures retain the existing deterministic prose fallback. The fallback is local code, not another billed provider.

## Frontend Experience

The connection control joins the top bar beside `New trip` and remains usable on dashboard and trip routes.

- Disconnected: a black `Continue with ChatGPT` button with a simple OpenAI-style knot mark and no invented brand claims.
- Connected: a quiet account chip reading `Using ChatGPT plan` and the selected model.
- Open panel: account identity, model selector, `Manage usage` link to `https://chatgpt.com/settings/usage`, and `Disconnect`.
- Scope declined: show that the account is connected but plan access was not granted, with a `Continue with ChatGPT` retry action.
- Callback success: show one accessible welcome dialog saying `You’re using your ChatGPT plan.` and remove the query marker from browser history when dismissed.
- Callback failure: show an actionable inline notice without exposing raw OAuth payloads.

The visual treatment extends TripWise's existing Fraunces/Manrope typography and sea-green/coral palette. The black connection button is the single new focal element. The panel uses the same rounded geometry as existing dialogs, includes keyboard focus and Escape handling, and collapses cleanly on narrow screens.

## Failure Handling and Security

- State, nonce, and PKCE values use cryptographically secure randomness and are never logged.
- OAuth transactions expire after ten minutes and are single-use.
- Tokens remain in backend memory or the protected credential file; browser storage and frontend state receive none.
- ID tokens are validated against OpenAI JWKS with RS256, exact issuer, the issued client audience, expiry, nonce, and subject checks.
- API errors use safe, user-actionable messages. Raw token responses, JWTs, and authorization codes do not enter logs or redirects.
- Model selection rejects any slug not returned as listable for the active account.
- Credential parsing fails closed: invalid or partial session data cannot enable the provider.
- No real network request occurs in automated tests.

## Configuration

New settings use these defaults:

- `TRIPWISE_CHATGPT_CREDENTIALS_PATH=.tripwise/chatgpt-credentials.json`
- `TRIPWISE_CHATGPT_REDIRECT_URI=http://127.0.0.1:8000/api/v1/auth/chatgpt/callback`
- `TRIPWISE_FRONTEND_URL=http://localhost:5173`

`PyJWT[crypto]>=2.10,<3` provides RS256/JWKS validation. The existing OpenAI SDK remains the inference client. Docker mounts `backend/.tripwise` at `/app/.tripwise` so credentials survive a backend container rebuild without leaving the project.

## Test Strategy

Backend tests cover atomic permissions, host-ID stability, PKCE construction, state expiry/replay, callback client-ID rules, JWKS validation inputs, missing scope, model filtering, safe status serialization, refresh serialization/rotation, model selection, revocation behavior, provider priority, stream completion, and local fallback.

Frontend tests cover the disconnected action, connected account panel, model selection, disconnect, scope-declined recovery, welcome dialog, error notice, and absence of secrets in browser-visible state. The final release gate runs backend tests and Ruff plus frontend tests, typecheck, lint, and production build, then inspects the live UI at desktop and mobile widths.
