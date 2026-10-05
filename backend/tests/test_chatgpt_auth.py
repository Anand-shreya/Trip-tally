from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from time import sleep
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.chatgpt.models import ChatGPTCredentials
from app.chatgpt.service import ChatGPTService, validate_id_token
from app.chatgpt.store import CredentialStore

REDIRECT_URI = "http://127.0.0.1:8000/api/v1/auth/chatgpt/callback"


def claims_validator(_token: str, *, client_id: str, nonce: str):
    assert client_id == "issued-client"
    assert nonce
    return {
        "sub": "account-subject",
        "email": "traveler@example.com",
        "name": "TripWise Traveler",
    }


def make_service(tmp_path, handler, *, credentials=None, validator=claims_validator):
    store = CredentialStore(tmp_path / "credentials.json")
    if credentials is not None:
        store.save(credentials)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ChatGPTService(
        store=store,
        redirect_uri=REDIRECT_URI,
        http_client=client,
        token_validator=validator,
    )


def successful_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/oauth/token"):
        return httpx.Response(
            200,
            json={
                "id_token": "signed-id-token",
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
                "scope": (
                    "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
                ),
            },
        )
    if request.url.path == "/v1/models":
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "slug": "gpt-hidden",
                        "display_name": "Hidden",
                        "visibility": "hidden",
                    },
                    {
                        "slug": "gpt-second",
                        "display_name": "Second",
                        "visibility": "list",
                    },
                    {
                        "slug": "gpt-first",
                        "display_name": "First",
                        "visibility": "list",
                    },
                    {
                        "slug": "gpt-second",
                        "display_name": "Second",
                        "visibility": "list",
                    },
                ]
            },
        )
    raise AssertionError(f"Unexpected request: {request.method} {request.url}")


def test_initial_authorization_uses_dynamic_registration_and_pkce(tmp_path):
    service = make_service(tmp_path, successful_handler)

    start = service.start_authorization()
    query = parse_qs(urlsplit(start.url).query)

    assert query["client_id"] == ["dynamic_agent_client"]
    assert query["agent_name_hint"] == ["TripWise"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == ["https://api.openai.com/v1"]
    assert query["redirect_uri"] == [REDIRECT_URI]
    assert query["state"] == [start.state]
    assert query["scope"] == [
        "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
    ]
    assert query["ext_agent_host_id"][0].startswith("urn:uuid:")


def test_returning_authorization_uses_issued_client_without_registration_hint(tmp_path):
    registered = ChatGPTCredentials(
        host_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        client_id="issued-client",
    )
    service = make_service(tmp_path, successful_handler, credentials=registered)

    query = parse_qs(urlsplit(service.start_authorization().url).query)

    assert query["client_id"] == ["issued-client"]
    assert "agent_name_hint" not in query


def test_returning_callback_without_client_id_uses_stored_issued_client(tmp_path):
    registered = ChatGPTCredentials(
        host_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        client_id="issued-client",
        subject="account-subject",
    )
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            observed.update(parse_qs(request.content.decode()))
        return successful_handler(request)

    service = make_service(tmp_path, handler, credentials=registered)
    start = service.start_authorization()

    result = service.complete_authorization(
        code="authorization-code",
        state=start.state,
        callback_client_id=None,
    )

    assert result.plan_enabled is True
    assert observed["client_id"] == ["issued-client"]


def test_returning_callback_rejects_a_different_issued_client(tmp_path):
    registered = ChatGPTCredentials(
        host_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        client_id="issued-client",
        subject="account-subject",
    )
    service = make_service(tmp_path, successful_handler, credentials=registered)
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id="different-client",
        )

    assert getattr(error.value, "reason", None) == "registration_incomplete"


def test_callback_filters_models_and_marks_direct_scope(tmp_path):
    service = make_service(tmp_path, successful_handler)
    start = service.start_authorization()

    result = service.complete_authorization(
        code="authorization-code",
        state=start.state,
        callback_client_id="issued-client",
    )

    assert result.models == ["gpt-second", "gpt-first"]
    assert result.plan_enabled is True
    assert result.selected_model == "gpt-second"
    assert result.email == "traveler@example.com"


def test_code_exchange_uses_issued_client_original_pkce_and_resource(tmp_path):
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            observed.update(parse_qs(request.content.decode()))
        return successful_handler(request)

    service = make_service(tmp_path, handler)
    start = service.start_authorization()

    service.complete_authorization(
        code="authorization-code",
        state=start.state,
        callback_client_id="issued-client",
    )

    assert observed["client_id"] == ["issued-client"]
    assert observed["code"] == ["authorization-code"]
    assert observed["redirect_uri"] == [REDIRECT_URI]
    assert observed["code_verifier"][0]
    assert observed["resource"] == ["https://api.openai.com/v1"]


def test_missing_direct_scope_keeps_identity_but_disables_plan(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/oauth/token")
        return httpx.Response(
            200,
            json={
                "id_token": "signed-id-token",
                "access_token": "identity-access",
                "refresh_token": "identity-refresh",
                "expires_in": 3600,
                "scope": "openid profile email offline_access",
            },
        )

    service = make_service(tmp_path, handler)
    start = service.start_authorization()

    result = service.complete_authorization(
        code="authorization-code",
        state=start.state,
        callback_client_id="issued-client",
    )

    assert result.signed_in is True
    assert result.plan_enabled is False
    assert result.state == "scope_required"
    assert result.models == []


def test_direct_scope_without_listable_models_has_a_distinct_state(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            return successful_handler(request)
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "slug": "gpt-hidden",
                            "display_name": "Hidden",
                            "visibility": "hidden",
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = make_service(tmp_path, handler)
    start = service.start_authorization()

    result = service.complete_authorization(
        code="authorization-code",
        state=start.state,
        callback_client_id="issued-client",
    )

    assert result.signed_in is True
    assert result.state == "model_required"
    assert result.models == []


def test_initial_registration_ends_after_first_successful_callback(tmp_path):
    service = make_service(tmp_path, successful_handler)

    assert service.is_initial_registration() is True
    start = service.start_authorization()
    service.complete_authorization(
        code="authorization-code",
        state=start.state,
        callback_client_id="issued-client",
    )

    assert service.is_initial_registration() is False


def test_initial_callback_rejects_registration_placeholder(tmp_path):
    service = make_service(tmp_path, successful_handler)
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id="dynamic_agent_client",
        )

    assert getattr(error.value, "reason", None) == "registration_incomplete"
    assert service.status().signed_in is False


def test_token_validation_failure_does_not_replace_existing_registration(tmp_path):
    registered = ChatGPTCredentials(
        host_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        client_id="issued-client",
    )

    def invalid_validator(_token: str, *, client_id: str, nonce: str):
        raise ValueError("ID token nonce did not match")

    service = make_service(
        tmp_path,
        successful_handler,
        credentials=registered,
        validator=invalid_validator,
    )
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id="issued-client",
        )

    assert getattr(error.value, "reason", None) == "identity_validation_failed"
    assert service.store.load() == registered


def test_returning_callback_rejects_a_different_verified_account(tmp_path):
    registered = ChatGPTCredentials(
        host_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        client_id="issued-client",
        subject="original-account",
    )

    def changed_account_validator(_token: str, *, client_id: str, nonce: str):
        return {"sub": "different-account", "nonce": nonce}

    service = make_service(
        tmp_path,
        successful_handler,
        credentials=registered,
        validator=changed_account_validator,
    )
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id=None,
        )

    assert getattr(error.value, "reason", None) == "identity_validation_failed"
    assert service.store.load() == registered


def test_model_discovery_failure_retains_validated_connection(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/token"):
            return successful_handler(request)
        if request.url.path == "/v1/models":
            return httpx.Response(503, json={"error": {"code": "temporarily_unavailable"}})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    service = make_service(tmp_path, handler)
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id="issued-client",
        )

    assert getattr(error.value, "reason", None) == "model_discovery_failed"
    stored = service.store.load()
    assert stored.client_id == "issued-client"
    assert stored.subject == "account-subject"
    assert stored.access_token == "access-token"
    assert stored.models == []


@pytest.mark.parametrize(
    ("response", "expected_reason"),
    [
        (httpx.Response(400, json={"error": "invalid_grant"}), "token_exchange_invalid_grant"),
        (
            httpx.Response(401, json={"error": "invalid_client"}),
            "token_exchange_invalid_client",
        ),
        (httpx.Response(503, text="private-upstream-detail"), "token_exchange_unavailable"),
        (httpx.Response(400, json={"error": "unsupported_error"}), "token_exchange_failed"),
    ],
)
def test_token_exchange_failure_has_a_safe_stage(tmp_path, response, expected_reason):
    service = make_service(
        tmp_path,
        lambda _request: response,
    )
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id="issued-client",
        )

    assert getattr(error.value, "reason", None) == expected_reason


def test_token_exchange_network_failure_is_safely_classified(tmp_path):
    def unavailable(request: httpx.Request):
        raise httpx.ConnectError("private-network-detail", request=request)

    service = make_service(tmp_path, unavailable)
    start = service.start_authorization()

    with pytest.raises(ValueError) as error:
        service.complete_authorization(
            code="authorization-code",
            state=start.state,
            callback_client_id="issued-client",
        )

    assert getattr(error.value, "reason", None) == "token_exchange_unavailable"


def test_failed_initial_exchange_retains_issued_client_for_retry(tmp_path):
    service = make_service(
        tmp_path,
        lambda _request: httpx.Response(400, json={"error": "invalid_grant"}),
    )
    first = service.start_authorization()

    with pytest.raises(ValueError):
        service.complete_authorization(
            code="authorization-code",
            state=first.state,
            callback_client_id="issued-client",
        )

    retry_query = parse_qs(urlsplit(service.start_authorization().url).query)
    assert retry_query["client_id"] == ["issued-client"]
    assert "agent_name_hint" not in retry_query
    assert service.status().signed_in is False


def test_validate_id_token_checks_jwks_issuer_audience_and_nonce(monkeypatch):
    observed = {}

    class SigningKey:
        key = "public-key"

    class JWKClient:
        def __init__(self, url):
            observed["jwks_url"] = url

        def get_signing_key_from_jwt(self, token):
            observed["token"] = token
            return SigningKey()

    def decode(token, key, **kwargs):
        observed["decode"] = (token, key, kwargs)
        return {"sub": "account-subject", "nonce": "expected-nonce"}

    monkeypatch.setattr("app.chatgpt.service.jwt.PyJWKClient", JWKClient)
    monkeypatch.setattr("app.chatgpt.service.jwt.decode", decode)

    claims = validate_id_token(
        "signed-token",
        client_id="issued-client",
        nonce="expected-nonce",
    )

    assert claims["sub"] == "account-subject"
    assert observed["jwks_url"] == "https://auth.openai.com/.well-known/jwks.json"
    assert observed["decode"][2] == {
        "algorithms": ["RS256"],
        "audience": "issued-client",
        "issuer": "https://auth.openai.com",
    }


def expired_credentials() -> ChatGPTCredentials:
    return ChatGPTCredentials(
        host_id="urn:uuid:00000000-0000-0000-0000-000000000001",
        client_id="issued-client",
        subject="account-subject",
        email="traveler@example.com",
        name="TripWise Traveler",
        id_token="id-token",
        access_token="expired-access",
        refresh_token="refresh-token",
        scopes=[
            "openid",
            "profile",
            "email",
            "offline_access",
            "resource.invoke",
            "chatgpt.tokens.use.direct",
        ],
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
        models=["gpt-listable"],
        selected_model="gpt-listable",
    )


def test_refresh_is_serialized_and_persists_rotated_token(tmp_path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        assert request.url.path.endswith("/oauth/token")
        form = parse_qs(request.content.decode())
        assert form["grant_type"] == ["refresh_token"]
        assert form["client_id"] == ["issued-client"]
        assert form["refresh_token"] == ["refresh-token"]
        assert form["resource"] == ["https://api.openai.com/v1"]
        calls += 1
        return httpx.Response(
            200,
            json={
                "access_token": "rotated-access",
                "refresh_token": "rotated-refresh",
                "expires_in": 3600,
                "scope": "openid chatgpt.tokens.use.direct",
            },
        )

    service = make_service(tmp_path, handler, credentials=expired_credentials())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.refresh_access_token(), range(2)))

    assert calls == 1
    assert results == [("rotated-access", "gpt-listable")] * 2
    assert service.store.load().refresh_token == "rotated-refresh"


def test_refresh_is_serialized_across_service_instances(tmp_path):
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        sleep(0.05)
        return httpx.Response(
            200,
            json={
                "access_token": "rotated-access",
                "refresh_token": "rotated-refresh",
                "expires_in": 3600,
                "scope": "openid chatgpt.tokens.use.direct",
            },
        )

    first = make_service(tmp_path, handler, credentials=expired_credentials())
    second = make_service(tmp_path, handler)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda service: service.refresh_access_token(), [first, second]))

    assert calls == 1
    assert results == [("rotated-access", "gpt-listable")] * 2


def test_select_model_rejects_unlisted_slug(tmp_path):
    service = make_service(tmp_path, successful_handler, credentials=expired_credentials())

    with pytest.raises(ValueError, match="not available"):
        service.select_model("hidden-model")


def test_select_model_persists_listed_slug(tmp_path):
    credentials = expired_credentials().model_copy(
        update={"models": ["gpt-first", "gpt-second"], "selected_model": "gpt-first"}
    )
    service = make_service(tmp_path, successful_handler, credentials=credentials)

    status = service.select_model("gpt-second")

    assert status.selected_model == "gpt-second"
    assert service.store.load().selected_model == "gpt-second"


def test_failed_revoke_keeps_local_session(tmp_path):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    service = make_service(tmp_path, handler, credentials=expired_credentials())

    with pytest.raises(RuntimeError, match="disconnect"):
        service.disconnect()

    assert service.status().signed_in is True
    assert service.store.load().refresh_token == "refresh-token"


def test_successful_revoke_clears_tokens_but_retains_registration(tmp_path):
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(parse_qs(request.content.decode()))
        return httpx.Response(200, json={"revoked": True})

    service = make_service(tmp_path, handler, credentials=expired_credentials())

    status = service.disconnect()

    assert observed == {
        "client_id": ["issued-client"],
        "token": ["refresh-token"],
        "token_type_hint": ["refresh_token"],
    }
    assert status.state == "disconnected"
    assert service.store.load().client_id == "issued-client"
    assert service.store.load().refresh_token is None
