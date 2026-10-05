# TripWise Sign in with ChatGPT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let TripWise securely use an eligible user's ChatGPT plan for AI itinerary and summary generation through Sign in with ChatGPT.

**Architecture:** A project-local backend package owns dynamic-client OAuth, protected credentials, refresh, revocation, model discovery, and safe status. The existing AI adapter consumes a refreshed OAuth token before considering the explicitly enabled API-key path, while a React top-bar control owns only connection status and user actions.

**Tech Stack:** FastAPI, Pydantic 2, httpx, PyJWT with cryptography, OpenAI Python SDK, React 19, TanStack Query, TypeScript, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-05-chatgpt-sign-in-design.md`

## Global Constraints

- Change files only inside `/Users/shreyaanand/Desktop/Go-pract/Projects/TripWise`.
- Never read, send, log, or exercise the stored OpenAI API key.
- Use `http://127.0.0.1:8000/api/v1/auth/chatgpt/callback` exactly as the OAuth loopback callback.
- Use OAuth scopes `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct` and resource `https://api.openai.com/v1`.
- Store tokens only in `backend/.tripwise/chatgpt-credentials.json` by default, atomically and with mode `0600`.
- Use `Continue with ChatGPT` for the disconnected action and `You’re using your ChatGPT plan.` after first connection.
- Responses inference must stream, set `store=False`, send complete input history, and require `response.completed`.
- Automated tests must use local fakes; they must not start a real OAuth flow or call OpenAI.
- Keep the legacy API-key path disabled unless `TRIPWISE_OPENAI_ENABLED=true`; never fall through to it after a connected ChatGPT-plan failure.
- Preserve deterministic local behavior when no AI provider is intentionally enabled.

## Review Focus

- A callback with a valid query-state but missing/mismatched state cookie must be rejected before token exchange; Task 2 tests `test_callback_rejects_mismatched_state_cookie`.
- A second callback using the same state must fail as a replay; Task 1 tests `test_transaction_is_consumed_once`.
- Two inference callers near expiry must cause only one refresh and both receive the rotated access token; Task 2 tests `test_refresh_is_serialized`.
- A stream that yields parsed output without `response.completed` must be rejected; Task 3 tests `test_stream_requires_completed_event`.
- The frontend must never render or retain token/client/host fields even if a malformed status payload contains them; Task 4 tests only the declared safe status shape and scans rendered text for representative secrets.

---

## File Structure

- `backend/app/chatgpt/models.py`: private credential model and public safe status/model request schemas.
- `backend/app/chatgpt/store.py`: atomic, permission-restricted JSON persistence.
- `backend/app/chatgpt/transactions.py`: PKCE values and expiring, single-use state transactions.
- `backend/app/chatgpt/service.py`: authorization URL, callback exchange, JWT validation, model discovery, refresh, model selection, revocation, and inference credentials.
- `backend/app/chatgpt/deps.py`: cached production service construction.
- `backend/app/api/chatgpt.py`: browser-facing routes and safe redirect behavior.
- `backend/app/providers/ai.py`: provider priority and streamed structured Responses helper.
- `frontend/src/components/ChatGPTConnection.tsx`: connection trigger, panel, callback notices, model selection, and disconnect.
- `frontend/src/lib/chatgpt.ts`: safe API types and connection query/mutation functions.
- `frontend/src/app/AppShell.tsx`: top-bar placement.
- `frontend/src/styles.css`: responsive component-specific styling.
- `backend/tests/test_chatgpt_store.py`, `backend/tests/test_chatgpt_auth.py`, `backend/tests/test_chatgpt_api.py`: backend behavior tests.
- `frontend/tests/chatgpt-connection.test.tsx`: browser interaction tests.

### Task 1: Protected Credentials and OAuth Transactions

**Files:**
- Create: `backend/app/chatgpt/__init__.py`
- Create: `backend/app/chatgpt/models.py`
- Create: `backend/app/chatgpt/store.py`
- Create: `backend/app/chatgpt/transactions.py`
- Create: `backend/tests/test_chatgpt_store.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `ChatGPTCredentials`, `ChatGPTStatus`, `ChatGPTModelSelection`, `CredentialStore.load/save/ensure_host_id/clear_session`, `AuthorizationTransactions.create/consume`, and `OAuthTransaction`.
- Consumes: Pydantic models and standard-library filesystem, UUID, secrets, hashing, locking, and UTC time APIs.

- [ ] **Step 1: Write the failing storage tests**

```python
def test_store_writes_credentials_atomically_with_owner_only_permissions(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")
    credentials = ChatGPTCredentials(host_id="urn:uuid:00000000-0000-0000-0000-000000000001")
    store.save(credentials)
    assert store.load() == credentials
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600

def test_clear_session_retains_registration(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")
    store.save(connected_credentials())
    cleared = store.clear_session()
    assert cleared.host_id.startswith("urn:uuid:")
    assert cleared.client_id == "issued-client"
    assert cleared.access_token is None
    assert cleared.subject is None
```

- [ ] **Step 2: Run the storage tests to verify RED**

Run: `.venv/bin/python -m pytest backend/tests/test_chatgpt_store.py -q`

Expected: FAIL during import because `app.chatgpt.store` does not exist.

- [ ] **Step 3: Implement credential models and protected persistence**

```python
class ChatGPTCredentials(BaseModel):
    host_id: str
    client_id: str | None = None
    subject: str | None = None
    email: str | None = None
    name: str | None = None
    id_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    models: list[str] = Field(default_factory=list)
    selected_model: str | None = None

class CredentialStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()

    def load(self) -> ChatGPTCredentials | None:
        with self._lock:
            if not self.path.exists():
                return None
            return ChatGPTCredentials.model_validate_json(self.path.read_text())

    def save(self, credentials: ChatGPTCredentials) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(credentials.model_dump_json(indent=2))
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)

    def ensure_host_id(self) -> ChatGPTCredentials:
        current = self.load()
        if current is not None:
            return current
        created = ChatGPTCredentials(host_id=f"urn:uuid:{uuid4()}")
        self.save(created)
        return created

    def clear_session(self) -> ChatGPTCredentials:
        current = self.ensure_host_id()
        cleared = ChatGPTCredentials(host_id=current.host_id, client_id=current.client_id)
        self.save(cleared)
        return cleared
```

Use the code above with a temporary file in the target directory, owner-only mode, atomic replacement, and a process lock. Reject `client_id="dynamic_agent_client"` in the Pydantic model validator.

- [ ] **Step 4: Add failing transaction tests**

```python
def test_transaction_builds_s256_pkce():
    transaction = AuthorizationTransactions().create("http://127.0.0.1:8000/callback")
    expected = base64.urlsafe_b64encode(hashlib.sha256(transaction.verifier.encode()).digest()).rstrip(b"=").decode()
    assert transaction.challenge == expected

def test_transaction_is_consumed_once():
    transactions = AuthorizationTransactions()
    transaction = transactions.create("http://127.0.0.1:8000/callback")
    assert transactions.consume(transaction.state) == transaction
    with pytest.raises(ValueError, match="expired or already used"):
        transactions.consume(transaction.state)
```

- [ ] **Step 5: Run transaction tests to verify RED**

Run: `.venv/bin/python -m pytest backend/tests/test_chatgpt_store.py -q`

Expected: FAIL because `AuthorizationTransactions` is missing.

- [ ] **Step 6: Implement expiring one-time transactions**

```python
@dataclass(frozen=True)
class OAuthTransaction:
    state: str
    nonce: str
    verifier: str
    challenge: str
    redirect_uri: str
    created_at: datetime

class AuthorizationTransactions:
    def __init__(self, ttl: timedelta = timedelta(minutes=10)):
        self._ttl = ttl
        self._pending: dict[str, OAuthTransaction] = {}
        self._lock = Lock()

    def create(self, redirect_uri: str) -> OAuthTransaction:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        transaction = OAuthTransaction(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            verifier=verifier,
            challenge=challenge,
            redirect_uri=redirect_uri,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._pending[transaction.state] = transaction
        return transaction

    def consume(self, state: str) -> OAuthTransaction:
        with self._lock:
            transaction = self._pending.pop(state, None)
        if transaction is None or datetime.now(UTC) - transaction.created_at > self._ttl:
            raise ValueError("Authorization request expired or already used")
        return transaction
```

Generate values with `secrets.token_urlsafe`, retain them under a lock, remove on consumption, and reject entries older than ten minutes.

- [ ] **Step 7: Ignore runtime credentials and verify GREEN**

Add `.tripwise/` to `.gitignore` and run:

`.venv/bin/python -m pytest backend/tests/test_chatgpt_store.py -q`

Expected: all Task 1 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add .gitignore backend/app/chatgpt backend/tests/test_chatgpt_store.py
git commit -m "feat: add protected ChatGPT credential store"
```

### Task 2: OAuth Service and HTTP Routes

**Files:**
- Create: `backend/app/chatgpt/service.py`
- Create: `backend/app/chatgpt/deps.py`
- Create: `backend/app/api/chatgpt.py`
- Create: `backend/tests/test_chatgpt_auth.py`
- Create: `backend/tests/test_chatgpt_api.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/__init__.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Consumes: Task 1's credential and transaction APIs.
- Produces: `AuthorizationStart(url: str, state: str)`, `ChatGPTService.start_authorization/complete_authorization/status/select_model/refresh_access_token/disconnect/inference_credentials`, `get_chatgpt_service()`, and `/api/v1/auth/chatgpt/*`.

- [ ] **Step 1: Write failing authorization-service tests**

```python
def test_initial_authorization_uses_dynamic_registration_and_pkce(service):
    start = service.start_authorization()
    query = parse_qs(urlsplit(start.url).query)
    assert query["client_id"] == ["dynamic_agent_client"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == ["https://api.openai.com/v1"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/api/v1/auth/chatgpt/callback"]

def test_callback_filters_models_and_marks_direct_scope(service_with_fake_http, signed_id_token):
    pending = service_with_fake_http.start_authorization()
    result = service_with_fake_http.complete_authorization(
        code="authorization-code", state=pending.state, callback_client_id="issued-client"
    )
    assert result.models == ["gpt-listable"]
    assert result.plan_enabled is True
    assert result.selected_model == "gpt-listable"

def test_missing_direct_scope_keeps_identity_but_disables_plan(service_with_fake_http):
    pending = service_with_fake_http.start_authorization()
    result = service_with_fake_http.complete_authorization(
        code="authorization-code", state=pending.state, callback_client_id="issued-client"
    )
    assert result.signed_in is True
    assert result.plan_enabled is False
```

Use injected token validation and `httpx.MockTransport`; assert on resulting service behavior, while inspecting request bodies only where they form TripWise's protocol boundary.

- [ ] **Step 2: Run service tests to verify RED**

Run: `.venv/bin/python -m pytest backend/tests/test_chatgpt_auth.py -q`

Expected: FAIL because `ChatGPTService` does not exist.

- [ ] **Step 3: Implement the OAuth service and JWT verification**

```python
def validate_id_token(token: str, *, client_id: str, nonce: str) -> dict[str, object]:
    signing_key = jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer="https://auth.openai.com",
    )
    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not hmac.compare_digest(token_nonce, nonce):
        raise ValueError("ID token nonce did not match")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise ValueError("ID token subject is missing")
    return claims
```

Implement `ChatGPTService.start_authorization`, `complete_authorization`, `status`, `select_model`, `refresh_access_token`, `disconnect`, and `inference_credentials` with the exact signatures in the Interfaces block. Use the validator above. Parse scope responses from either space-delimited strings or lists. Fetch `/v1/models`, sort unique entries whose `visibility` is `list`, and persist only after identity validation succeeds.

- [ ] **Step 4: Add refresh, selection, and revocation tests**

```python
def test_refresh_is_serialized(service, fake_refresh_http):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.refresh_access_token(), range(2)))
    assert fake_refresh_http.refresh_calls == 1
    assert results == [("rotated-access", "gpt-listable")] * 2

def test_select_model_rejects_unlisted_slug(service):
    with pytest.raises(ValueError, match="not available"):
        service.select_model("hidden-model")

def test_failed_revoke_keeps_local_session(service):
    with pytest.raises(RuntimeError, match="disconnect"):
        service.disconnect()
    assert service.status().signed_in is True
```

- [ ] **Step 5: Run service tests and make them GREEN**

Run: `.venv/bin/python -m pytest backend/tests/test_chatgpt_auth.py -q`

Expected: all authorization, refresh, model, and disconnect tests PASS.

- [ ] **Step 6: Write failing route tests**

```python
def test_start_sets_http_only_state_cookie_and_redirects(client):
    response = client.get("/api/v1/auth/chatgpt/start", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://auth.openai.com/")
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]

def test_callback_rejects_mismatched_state_cookie(client, fake_service):
    response = client.get("/api/v1/auth/chatgpt/callback?code=x&state=query", cookies={"tripwise_chatgpt_state": "cookie"}, follow_redirects=False)
    assert response.status_code == 307
    assert "chatgpt=error" in response.headers["location"]
    assert fake_service.exchange_calls == 0

def test_status_never_returns_credentials(client):
    body = client.get("/api/v1/auth/chatgpt/status").json()
    assert not {"access_token", "refresh_token", "client_id", "host_id"} & body.keys()
```

- [ ] **Step 7: Run route tests to verify RED**

Run: `.venv/bin/python -m pytest backend/tests/test_chatgpt_api.py -q`

Expected: FAIL with a 404 for `/api/v1/auth/chatgpt/status`.

- [ ] **Step 8: Implement routes, settings, dependency, and dependency declaration**

Add settings for credential path, redirect URI, and frontend URL. Register the router. Add `PyJWT[crypto]>=2.10,<3`. Callback error redirects must use stable reason codes such as `state_mismatch`, `authorization_failed`, and `scope_required`, never exception text.

- [ ] **Step 9: Verify Task 2 GREEN**

Run: `.venv/bin/python -m pytest backend/tests/test_chatgpt_auth.py backend/tests/test_chatgpt_api.py -q`

Expected: all Task 2 tests PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/chatgpt backend/app/api backend/app/core/config.py backend/pyproject.toml backend/tests/test_chatgpt_auth.py backend/tests/test_chatgpt_api.py
git commit -m "feat: implement ChatGPT OAuth flow"
```

### Task 3: Streamed ChatGPT-Plan Inference

**Files:**
- Modify: `backend/app/providers/ai.py`
- Modify: `backend/tests/test_itinerary_summary.py`

**Interfaces:**
- Consumes: Task 2's `get_chatgpt_service().inference_credentials()` returning `(access_token, selected_model)` or `None`.
- Produces: OAuth-first provider selection and `_stream_parsed` for schema-validated streamed Responses.

- [ ] **Step 1: Replace adapter expectations with failing stream tests**

```python
def test_chatgpt_stream_sets_store_false_and_returns_only_after_completion(db):
    stream = FakeStream(events=[SimpleNamespace(type="response.completed")], parsed=expected)
    client = SimpleNamespace(responses=FakeResponses(stream))
    assert generate_itinerary(trip, trip.places, client=client, model="gpt-test") == expected
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["text_format"] is ItineraryPlan

def test_stream_requires_completed_event(db):
    stream = FakeStream(events=[], parsed=expected)
    with pytest.raises(RuntimeError, match="before completion"):
        generate_itinerary(trip, trip.places, client=SimpleNamespace(responses=FakeResponses(stream)))

def test_connected_chatgpt_precedes_enabled_api_key(monkeypatch):
    monkeypatch the ChatGPT dependency to return ("oauth-token", "gpt-plan") and the OpenAI constructor to record arguments
    assert constructor arguments include api_key="oauth-token", base_url="https://api.openai.com/v1", max_retries=0
```

- [ ] **Step 2: Run focused adapter tests to verify RED**

Run: `.venv/bin/python -m pytest backend/tests/test_itinerary_summary.py -q`

Expected: FAIL because the adapter calls `responses.parse` and does not set `store=False`.

- [ ] **Step 3: Implement streamed inference and provider priority**

```python
def _stream_parsed(client, *, model: str, input: list[dict[str, str]], text_format: type[BaseModel]):
    completed = False
    with client.responses.stream(model=model, input=input, text_format=text_format, store=False) as stream:
        for event in stream:
            completed = completed or event.type == "response.completed"
        response = stream.get_final_response()
    if not completed:
        raise RuntimeError("OpenAI response stream ended before completion")
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no structured output")
    return response.output_parsed
```

When a ChatGPT connection exists, construct `OpenAI(api_key=token, base_url="https://api.openai.com/v1", max_retries=0)`. Do not catch that provider selection and continue into the legacy API-key path. Preserve summary's deterministic fallback and itinerary's durable failure behavior.

- [ ] **Step 4: Verify Task 3 GREEN and the full backend suite**

Run: `.venv/bin/python -m pytest backend/tests/test_itinerary_summary.py -q && .venv/bin/python -m pytest backend/tests -q`

Expected: focused adapter tests and the complete backend suite PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/providers/ai.py backend/tests/test_itinerary_summary.py
git commit -m "feat: use ChatGPT plan for streamed AI generation"
```

### Task 4: ChatGPT Connection UI

**Files:**
- Create: `frontend/src/components/ChatGPTConnection.tsx`
- Create: `frontend/src/lib/chatgpt.ts`
- Create: `frontend/tests/chatgpt-connection.test.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/lib/queryKeys.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: Task 2's status, model, disconnect, and start routes.
- Produces: top-bar connection UI with a safe status query and model/disconnect mutations.

- [ ] **Step 1: Write failing disconnected and connected interaction tests**

```tsx
it('starts the required ChatGPT connection flow', async () => {
  renderConnection({ signed_in: false, plan_enabled: false, models: [], selected_model: null })
  expect(await screen.findByRole('button', { name: 'Continue with ChatGPT' })).toBeInTheDocument()
})

it('shows plan state, selects a model, and disconnects', async () => {
  renderConnection(connectedStatus)
  await user.click(await screen.findByRole('button', { name: /using chatgpt plan/i }))
  expect(screen.getByRole('link', { name: 'Manage usage' })).toHaveAttribute('href', 'https://chatgpt.com/settings/usage')
  await user.selectOptions(screen.getByLabelText('Model'), 'gpt-second')
  await user.click(screen.getByRole('button', { name: 'Disconnect' }))
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/auth/chatgpt/disconnect'), expect.objectContaining({ method: 'POST' }))
})
```

- [ ] **Step 2: Run UI tests to verify RED**

Run: `PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend test -- chatgpt-connection.test.tsx`

Expected: FAIL because `ChatGPTConnection` does not exist.

- [ ] **Step 3: Implement the safe client and connection control**

```ts
export interface ChatGPTStatus {
  signed_in: boolean
  plan_enabled: boolean
  name: string | null
  email: string | null
  models: string[]
  selected_model: string | null
  manage_usage_url: string
}

export const CHATGPT_START_URL = 'http://127.0.0.1:8000/api/v1/auth/chatgpt/start'
```

Use TanStack Query for status and mutations. Start OAuth with `window.location.assign(CHATGPT_START_URL)`. The component must access only declared safe fields, close its panel on Escape/outside click, and expose status changes through text as well as color.

- [ ] **Step 4: Add callback, scope-declined, and secret-exclusion tests**

```tsx
it('welcomes the user after a successful callback and removes the marker', async () => {
  renderConnection(connectedStatus, '/?chatgpt=connected')
  expect(await screen.findByRole('dialog', { name: /chatgpt is connected/i })).toHaveTextContent("You’re using your ChatGPT plan.")
})

it('offers reconnection when direct plan scope was declined', async () => {
  renderConnection({ ...connectedStatus, plan_enabled: false })
  expect(await screen.findByText(/plan access wasn’t granted/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Continue with ChatGPT' })).toBeInTheDocument()
})

expect(document.body).not.toHaveTextContent('secret-access-token')
```

- [ ] **Step 5: Style the component using the TripWise design system**

Use true black `#000` only for the disconnected ChatGPT button. Use the existing `#14213d`, `#1e6f6d`, `#f8f7f2`, and border tones for the connected chip and panel. Preserve the 76px top-bar rhythm, stack actions on narrow screens, show visible focus, and honor the existing reduced-motion rule.

- [ ] **Step 6: Verify Task 4 GREEN and frontend quality gates**

Run: `PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend test && PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend run typecheck && PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend run lint`

Expected: all frontend tests PASS, typecheck exits 0, and ESLint exits 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src frontend/tests/chatgpt-connection.test.tsx
git commit -m "feat: add ChatGPT connection controls"
```

### Task 5: Configuration, Documentation, and Release Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: completed backend and frontend behavior.
- Produces: documented local setup, persistent Docker credential mount, and a verified running application.

- [ ] **Step 1: Update configuration and documentation**

Document the three new environment variables, account eligibility, the `Continue with ChatGPT` flow, project-local credential location, how to disconnect, deterministic fallback behavior, and the fact that ChatGPT plan usage is distinct from an OpenAI API key. Add `./backend/.tripwise:/app/.tripwise` to the backend and worker services.

- [ ] **Step 2: Install the declared backend dependency inside the project virtual environment**

Run: `.venv/bin/python -m pip install -e './backend[dev]'`

Expected: editable `tripwise-api` installation succeeds with PyJWT and cryptography available.

- [ ] **Step 3: Run the complete backend gate**

Run: `.venv/bin/ruff check backend && .venv/bin/ruff format --check backend && .venv/bin/python -m pytest backend/tests`

Expected: Ruff checks exit 0 and all backend tests PASS.

- [ ] **Step 4: Run the complete frontend gate**

Run: `PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend test && PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend run typecheck && PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend run lint && PATH='/Users/shreyaanand/.nvm/versions/node/v24.12.0/bin':$PATH npm --prefix frontend run build`

Expected: all frontend tests PASS, typecheck and lint exit 0, and Vite produces a production build.

- [ ] **Step 5: Verify configuration and live behavior**

Run: `docker compose config --quiet` and request `http://localhost:8000/api/v1/health` plus `http://localhost:8000/api/v1/auth/chatgpt/status`.

Expected: Compose configuration exits 0; health returns `status=ok`; ChatGPT status returns safe disconnected or connected fields without tokens.

Open `http://localhost:5173` in the existing in-app browser. Inspect desktop and mobile layouts, confirm `Continue with ChatGPT` or the connected plan chip is visible, and do not initiate real OAuth during verification.

- [ ] **Step 6: Commit**

```bash
git add .env.example README.md docker-compose.yml
git commit -m "docs: document ChatGPT plan connection"
```
