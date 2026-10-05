import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock


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
        now = datetime.now(UTC)
        transaction = OAuthTransaction(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            verifier=verifier,
            challenge=challenge,
            redirect_uri=redirect_uri,
            created_at=now,
        )
        with self._lock:
            cutoff = now - self._ttl
            self._pending = {
                state: item for state, item in self._pending.items() if item.created_at >= cutoff
            }
            self._pending[transaction.state] = transaction
        return transaction

    def consume(self, state: str) -> OAuthTransaction:
        with self._lock:
            transaction = self._pending.pop(state, None)
        if transaction is None or datetime.now(UTC) - transaction.created_at > self._ttl:
            raise ValueError("Authorization request expired or already used")
        return transaction
