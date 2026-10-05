import base64
import hashlib
import stat
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.chatgpt.models import ChatGPTCredentials
from app.chatgpt.store import CredentialStore

HOST_ID = "urn:uuid:00000000-0000-0000-0000-000000000001"


def connected_credentials() -> ChatGPTCredentials:
    return ChatGPTCredentials(
        host_id=HOST_ID,
        client_id="issued-client",
        subject="account-subject",
        email="traveler@example.com",
        name="TripWise Traveler",
        id_token="id-token",
        access_token="access-token",
        refresh_token="refresh-token",
        scopes=["openid", "chatgpt.tokens.use.direct"],
        expires_at=datetime(2026, 10, 5, 10, 30, tzinfo=UTC),
        models=["gpt-listable"],
        selected_model="gpt-listable",
    )


def test_store_writes_credentials_atomically_with_owner_only_permissions(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")
    credentials = ChatGPTCredentials(host_id=HOST_ID)

    store.save(credentials)

    assert store.load() == credentials
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert not store.path.with_suffix(".tmp").exists()


def test_clear_session_retains_registration(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")
    store.save(connected_credentials())

    cleared = store.clear_session()

    assert cleared.host_id == HOST_ID
    assert cleared.client_id == "issued-client"
    assert cleared.access_token is None
    assert cleared.subject is None
    assert cleared.models == []


def test_ensure_host_id_is_stable(tmp_path):
    store = CredentialStore(tmp_path / "credentials.json")

    first = store.ensure_host_id()
    second = store.ensure_host_id()

    assert first.host_id == second.host_id
    assert first.host_id.startswith("urn:uuid:")


def test_dynamic_registration_identifier_cannot_be_persisted():
    with pytest.raises(ValidationError, match="dynamic_agent_client"):
        ChatGPTCredentials(host_id=HOST_ID, client_id="dynamic_agent_client")


def test_transaction_builds_s256_pkce():
    from app.chatgpt.transactions import AuthorizationTransactions

    transaction = AuthorizationTransactions().create("http://127.0.0.1:8000/callback")
    digest = hashlib.sha256(transaction.verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    assert transaction.challenge == expected
    assert transaction.state != transaction.nonce


def test_transaction_is_consumed_once():
    from app.chatgpt.transactions import AuthorizationTransactions

    transactions = AuthorizationTransactions()
    transaction = transactions.create("http://127.0.0.1:8000/callback")

    assert transactions.consume(transaction.state) == transaction
    with pytest.raises(ValueError, match="expired or already used"):
        transactions.consume(transaction.state)


def test_expired_transaction_is_rejected():
    from app.chatgpt.transactions import AuthorizationTransactions

    transactions = AuthorizationTransactions(ttl=timedelta(seconds=-1))
    transaction = transactions.create("http://127.0.0.1:8000/callback")

    with pytest.raises(ValueError, match="expired or already used"):
        transactions.consume(transaction.state)
