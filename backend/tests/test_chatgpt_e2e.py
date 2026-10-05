import stat
import sys
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient

from app.chatgpt.deps import get_chatgpt_service
from app.chatgpt.service import ChatGPTService
from app.chatgpt.store import CredentialStore
from app.main import create_app
from app.providers import ai as ai_module
from app.schemas.itinerary import ActivityPlan, ItineraryDayPlan, ItineraryPlan


class CompletedStream:
    def __init__(self, parsed):
        self.parsed = parsed

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def __iter__(self):
        return iter([SimpleNamespace(type="response.completed")])

    def get_final_response(self):
        return SimpleNamespace(output_parsed=self.parsed)


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return CompletedStream(self.parsed)


def test_fake_sign_in_reaches_safe_status_and_streamed_first_inference(tmp_path, monkeypatch):
    observed = {"token_exchange": False, "model_catalog": False}

    def upstream(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["issued-client"]
            assert form["resource"] == ["https://api.openai.com/v1"]
            assert form["code_verifier"][0]
            observed["token_exchange"] = True
            return httpx.Response(
                200,
                json={
                    "id_token": "fake-id-token",
                    "access_token": "fake-access-token",
                    "refresh_token": "fake-refresh-token",
                    "expires_in": 3600,
                    "scope": (
                        "openid profile email offline_access resource.invoke "
                        "chatgpt.tokens.use.direct"
                    ),
                },
            )
        if request.url.path == "/v1/models":
            observed["model_catalog"] = True
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "slug": "gpt-visible",
                            "display_name": "GPT Visible",
                            "visibility": "list",
                        },
                        {
                            "slug": "gpt-hidden",
                            "display_name": "GPT Hidden",
                            "visibility": "hidden",
                        },
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    credentials_path = tmp_path / "credentials.json"
    service = ChatGPTService(
        store=CredentialStore(credentials_path),
        redirect_uri="http://127.0.0.1:8000/api/v1/auth/chatgpt/callback",
        http_client=httpx.Client(transport=httpx.MockTransport(upstream)),
        token_validator=lambda _token, *, client_id, nonce: {
            "sub": "account-subject",
            "email": "traveler@example.com",
            "name": "TripWise Traveler",
            "nonce": nonce,
            "aud": client_id,
        },
    )
    app = create_app(init_database=False)
    app.dependency_overrides[get_chatgpt_service] = lambda: service
    client = TestClient(app)

    started = client.get("/api/v1/auth/chatgpt/start", follow_redirects=False)
    authorization = urlsplit(started.headers["location"])
    authorization_query = parse_qs(authorization.query)
    assert authorization.netloc == "auth.openai.com"
    assert authorization_query["client_id"] == ["dynamic_agent_client"]
    assert authorization_query["resource"] == ["https://api.openai.com/v1"]

    callback = client.get(
        "/api/v1/auth/chatgpt/callback",
        params={
            "code": "one-time-code",
            "state": authorization_query["state"][0],
            "client_id": "issued-client",
        },
        follow_redirects=False,
    )
    assert callback.headers["location"] == ("http://localhost:5173/?chatgpt=connected&welcome=1")
    assert observed == {"token_exchange": True, "model_catalog": True}
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600

    status = client.get("/api/v1/auth/chatgpt/status")
    assert status.json() == {
        "state": "connected",
        "signed_in": True,
        "plan_enabled": True,
        "name": "TripWise Traveler",
        "email": "traveler@example.com",
        "models": ["gpt-visible"],
        "selected_model": "gpt-visible",
        "manage_usage_url": "https://chatgpt.com/settings/usage",
    }

    expected = ItineraryPlan(
        days=[
            ItineraryDayPlan(
                day=1,
                date=date(2027, 2, 14),
                title="A day in Kyoto",
                summary="Temples and local food.",
                activities=[
                    ActivityPlan(
                        title="Temple walk",
                        description="Visit a historic temple district.",
                        activity_type="SIGHTSEEING",
                        start_time="09:00",
                        end_time="12:00",
                        location_name="Kyoto",
                        latitude=35.0116,
                        longitude=135.7681,
                        estimated_cost=0,
                    )
                ],
            )
        ]
    )
    responses = FakeResponses(expected)

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url, max_retries):
            assert api_key == "fake-access-token"
            assert base_url == "https://api.openai.com/v1"
            assert max_retries == 0
            self.responses = responses

    monkeypatch.setattr(ai_module, "get_chatgpt_service", lambda: service)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    trip = SimpleNamespace(
        name="Kyoto weekend",
        destination="Kyoto",
        start_date=date(2027, 2, 14),
        number_of_days=1,
        base_currency="INR",
        budget=Decimal("50000"),
        weather_summary="Cool and clear.",
    )
    place = SimpleNamespace(
        name="Kyoto",
        description="Historic temples and neighborhoods",
        latitude=35.0116,
        longitude=135.7681,
        recommended_days=Decimal("1"),
        estimated_cost=Decimal("12000"),
        best_for=["Culture"],
    )

    result = ai_module.generate_itinerary(trip, [place])

    assert result == expected
    inference = responses.calls[0]
    assert inference["model"] == "gpt-visible"
    assert inference["store"] is False
    assert "Create a practical day-by-day travel itinerary" in inference["instructions"]
    assert [item["role"] for item in inference["input"]] == ["user"]
