from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from app.chatgpt.deps import get_chatgpt_service
from app.chatgpt.models import ChatGPTStatus
from app.chatgpt.service import AuthorizationStart, ChatGPTService
from app.chatgpt.store import CredentialStore
from app.main import create_app

CONNECTED = ChatGPTStatus(
    state="connected",
    signed_in=True,
    plan_enabled=True,
    name="TripWise Traveler",
    email="traveler@example.com",
    models=["gpt-listable", "gpt-second"],
    selected_model="gpt-listable",
)


@dataclass
class FakeService:
    current_status: ChatGPTStatus = field(default_factory=lambda: CONNECTED.model_copy(deep=True))
    exchange_calls: int = 0
    selected: str | None = None
    disconnect_error: bool = False
    initial_registration: bool = True

    def start_authorization(self):
        return AuthorizationStart(
            url="https://auth.openai.com/api/accounts/authorize?state=state-value",
            state="state-value",
        )

    def complete_authorization(self, *, code, state, callback_client_id):
        self.exchange_calls += 1
        assert code == "authorization-code"
        assert state == "state-value"
        assert callback_client_id == "issued-client"
        self.initial_registration = False
        return self.current_status

    def is_initial_registration(self):
        return self.initial_registration

    def status(self):
        return self.current_status

    def select_model(self, model):
        if model not in self.current_status.models:
            raise ValueError("Selected model is not available for this ChatGPT account")
        self.selected = model
        self.current_status = self.current_status.model_copy(update={"selected_model": model})
        return self.current_status

    def disconnect(self):
        if self.disconnect_error:
            raise RuntimeError("Unable to disconnect ChatGPT; try again")
        self.current_status = ChatGPTStatus(
            state="disconnected",
            signed_in=False,
            plan_enabled=False,
        )
        return self.current_status


@pytest.fixture
def chatgpt_client():
    service = FakeService()
    app = create_app(init_database=False)
    app.dependency_overrides[get_chatgpt_service] = lambda: service
    return TestClient(app), service


def test_start_sets_http_only_state_cookie_and_redirects(chatgpt_client):
    client, _service = chatgpt_client

    response = client.get("/api/v1/auth/chatgpt/start", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://auth.openai.com/")
    assert "tripwise_chatgpt_state=state-value" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Max-Age=600" in response.headers["set-cookie"]


def test_callback_rejects_mismatched_state_cookie(chatgpt_client):
    client, service = chatgpt_client
    client.cookies.set("tripwise_chatgpt_state", "cookie")

    response = client.get(
        "/api/v1/auth/chatgpt/callback?code=x&state=query&client_id=issued-client",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://localhost:5173/?chatgpt=error&reason=state_mismatch"
    )
    assert service.exchange_calls == 0


def test_callback_completes_connection_and_clears_cookie(chatgpt_client):
    client, service = chatgpt_client
    client.cookies.set("tripwise_chatgpt_state", "state-value")

    response = client.get(
        "/api/v1/auth/chatgpt/callback"
        "?code=authorization-code&state=state-value&client_id=issued-client",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == ("http://localhost:5173/?chatgpt=connected&welcome=1")
    assert "tripwise_chatgpt_state=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert service.exchange_calls == 1


def test_returning_callback_does_not_repeat_first_connection_welcome(chatgpt_client):
    client, service = chatgpt_client
    service.initial_registration = False
    client.cookies.set("tripwise_chatgpt_state", "state-value")

    response = client.get(
        "/api/v1/auth/chatgpt/callback"
        "?code=authorization-code&state=state-value&client_id=issued-client",
        follow_redirects=False,
    )

    assert response.headers["location"] == "http://localhost:5173/?chatgpt=connected"


def test_callback_maps_declined_scope_to_safe_frontend_state(chatgpt_client):
    client, service = chatgpt_client
    service.current_status = CONNECTED.model_copy(
        update={"state": "scope_required", "plan_enabled": False, "models": []}
    )
    client.cookies.set("tripwise_chatgpt_state", "state-value")

    response = client.get(
        "/api/v1/auth/chatgpt/callback"
        "?code=authorization-code&state=state-value&client_id=issued-client",
        follow_redirects=False,
    )

    assert response.headers["location"] == "http://localhost:5173/?chatgpt=scope_required"


def test_callback_maps_oauth_error_without_exposing_description(chatgpt_client):
    client, service = chatgpt_client
    client.cookies.set("tripwise_chatgpt_state", "state-value")

    response = client.get(
        "/api/v1/auth/chatgpt/callback"
        "?error=access_denied&error_description=secret-details&state=state-value",
        follow_redirects=False,
    )

    assert response.headers["location"] == (
        "http://localhost:5173/?chatgpt=error&reason=authorization_failed"
    )
    assert "secret-details" not in response.headers["location"]
    assert service.exchange_calls == 0


def test_callback_reports_token_exchange_stage_without_upstream_details(tmp_path):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "private-upstream-detail"},
        )
    )
    service = ChatGPTService(
        store=CredentialStore(tmp_path / "credentials.json"),
        redirect_uri="http://127.0.0.1:8000/api/v1/auth/chatgpt/callback",
        http_client=httpx.Client(transport=transport),
        token_validator=lambda *_args, **_kwargs: {},
    )
    app = create_app(init_database=False)
    app.dependency_overrides[get_chatgpt_service] = lambda: service
    client = TestClient(app)
    started = client.get("/api/v1/auth/chatgpt/start", follow_redirects=False)
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]

    response = client.get(
        "/api/v1/auth/chatgpt/callback",
        params={"code": "one-time-code", "state": state, "client_id": "issued-client"},
        follow_redirects=False,
    )

    assert response.headers["location"] == (
        "http://localhost:5173/?chatgpt=error&reason=token_exchange_invalid_grant"
    )
    assert "private-upstream-detail" not in response.headers["location"]


def test_status_never_returns_credentials(chatgpt_client):
    client, _service = chatgpt_client

    response = client.get("/api/v1/auth/chatgpt/status")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "connected"
    assert body["selected_model"] == "gpt-listable"
    assert not {"access_token", "refresh_token", "client_id", "host_id"} & body.keys()


def test_model_selection_accepts_only_an_available_model(chatgpt_client):
    client, service = chatgpt_client

    selected = client.post("/api/v1/auth/chatgpt/model", json={"model": "gpt-second"})
    rejected = client.post("/api/v1/auth/chatgpt/model", json={"model": "gpt-hidden"})

    assert selected.status_code == 200
    assert selected.json()["selected_model"] == "gpt-second"
    assert service.selected == "gpt-second"
    assert rejected.status_code == 400
    assert rejected.json() == {"detail": "Selected model is not available for this ChatGPT account"}


def test_disconnect_returns_safe_status_and_maps_revocation_failure(chatgpt_client):
    client, service = chatgpt_client

    disconnected = client.post("/api/v1/auth/chatgpt/disconnect")

    assert disconnected.status_code == 200
    assert disconnected.json()["state"] == "disconnected"

    service.current_status = CONNECTED
    service.disconnect_error = True
    failed = client.post("/api/v1/auth/chatgpt/disconnect")

    assert failed.status_code == 502
    assert failed.json() == {"detail": "Unable to disconnect ChatGPT; try again"}
