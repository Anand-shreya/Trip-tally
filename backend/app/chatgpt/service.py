import hmac
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.chatgpt.models import (
    DIRECT_TOKEN_SCOPE,
    ChatGPTCredentials,
    ChatGPTStatus,
)
from app.chatgpt.store import CredentialStore
from app.chatgpt.transactions import AuthorizationTransactions

AUTHORIZATION_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
REVOCATION_URL = "https://auth.openai.com/api/accounts/oauth/revoke"
JWKS_URL = "https://auth.openai.com/.well-known/jwks.json"
OPENAI_API_BASE = "https://api.openai.com/v1"
MODELS_URL = f"{OPENAI_API_BASE}/models"
OPENAI_ISSUER = "https://auth.openai.com"
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    "resource.invoke",
    DIRECT_TOKEN_SCOPE,
)

TokenValidator = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class AuthorizationStart:
    url: str
    state: str


def validate_id_token(token: str, *, client_id: str, nonce: str) -> dict[str, Any]:
    signing_key = jwt.PyJWKClient(JWKS_URL).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=OPENAI_ISSUER,
    )
    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not hmac.compare_digest(token_nonce, nonce):
        raise ValueError("ID token nonce did not match")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ValueError("ID token subject is missing")
    return claims


def _scopes_from(payload: dict[str, Any], fallback: list[str] | None = None) -> list[str]:
    raw_scopes = payload.get("scope", payload.get("scopes"))
    if raw_scopes is None:
        return list(fallback or [])
    if isinstance(raw_scopes, str):
        return sorted(set(raw_scopes.split()))
    if isinstance(raw_scopes, list) and all(isinstance(scope, str) for scope in raw_scopes):
        return sorted(set(raw_scopes))
    raise ValueError("OAuth token response contained invalid scopes")


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"OAuth token response is missing {field}")
    return value


def _expiry_from(payload: dict[str, Any]) -> datetime:
    expires_in = payload.get("expires_in")
    if not isinstance(expires_in, (int, float)) or expires_in <= 0:
        raise ValueError("OAuth token response contained invalid expires_in")
    return datetime.now(UTC) + timedelta(seconds=float(expires_in))


class ChatGPTService:
    def __init__(
        self,
        *,
        store: CredentialStore,
        redirect_uri: str,
        http_client: httpx.Client | None = None,
        transactions: AuthorizationTransactions | None = None,
        token_validator: TokenValidator = validate_id_token,
    ):
        self.store = store
        self.redirect_uri = redirect_uri
        self._http = http_client or httpx.Client(timeout=20.0)
        self._transactions = transactions or AuthorizationTransactions()
        self._token_validator = token_validator
        from threading import Lock

        self._refresh_lock = Lock()

    def start_authorization(self) -> AuthorizationStart:
        credentials = self.store.ensure_host_id()
        transaction = self._transactions.create(self.redirect_uri)
        client_id = credentials.client_id or DYNAMIC_CLIENT_ID
        query = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": transaction.redirect_uri,
            "scope": " ".join(SCOPES),
            "resource": OPENAI_API_BASE,
            "code_challenge": transaction.challenge,
            "code_challenge_method": "S256",
            "state": transaction.state,
            "nonce": transaction.nonce,
            "ext_agent_host_id": credentials.host_id,
        }
        if client_id == DYNAMIC_CLIENT_ID:
            query["agent_name_hint"] = "TripWise"
        return AuthorizationStart(
            url=f"{AUTHORIZATION_URL}?{urlencode(query)}",
            state=transaction.state,
        )

    def complete_authorization(
        self,
        *,
        code: str,
        state: str,
        callback_client_id: str | None,
    ) -> ChatGPTStatus:
        transaction = self._transactions.consume(state)
        current = self.store.ensure_host_id()
        issued_client_id = callback_client_id
        if (
            not issued_client_id
            or issued_client_id == DYNAMIC_CLIENT_ID
            or (current.client_id is not None and current.client_id != issued_client_id)
        ):
            raise ValueError("OpenAI callback did not return the expected issued client ID")

        response = self._http.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": issued_client_id,
                "code": code,
                "redirect_uri": transaction.redirect_uri,
                "code_verifier": transaction.verifier,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OAuth token response was not an object")

        id_token = _required_string(payload, "id_token")
        access_token = _required_string(payload, "access_token")
        refresh_token = _required_string(payload, "refresh_token")
        claims = self._token_validator(
            id_token,
            client_id=issued_client_id,
            nonce=transaction.nonce,
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ValueError("ID token subject is missing")
        scopes = _scopes_from(payload)
        models = self._list_models(access_token) if DIRECT_TOKEN_SCOPE in scopes else []
        selected_model = (
            current.selected_model if current.selected_model in models else next(iter(models), None)
        )
        credentials = ChatGPTCredentials(
            host_id=current.host_id,
            client_id=issued_client_id,
            subject=subject,
            email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            name=claims.get("name") if isinstance(claims.get("name"), str) else None,
            id_token=id_token,
            access_token=access_token,
            refresh_token=refresh_token,
            scopes=scopes,
            expires_at=_expiry_from(payload),
            models=models,
            selected_model=selected_model,
        )
        self.store.save(credentials)
        return self.status()

    def _list_models(self, access_token: str) -> list[str]:
        response = self._http.get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError("OpenAI models response did not contain a data list")
        return sorted(
            {
                row["id"]
                for row in rows
                if isinstance(row, dict)
                and row.get("visibility") == "list"
                and isinstance(row.get("id"), str)
                and row["id"]
            }
        )

    def status(self) -> ChatGPTStatus:
        credentials = self.store.load()
        if credentials is None or not credentials.signed_in:
            return ChatGPTStatus(
                state="disconnected",
                signed_in=False,
                plan_enabled=False,
            )
        plan_enabled = credentials.plan_enabled
        return ChatGPTStatus(
            state="connected" if plan_enabled else "scope_required",
            signed_in=True,
            plan_enabled=plan_enabled,
            name=credentials.name,
            email=credentials.email,
            models=credentials.models,
            selected_model=credentials.selected_model,
        )

    def select_model(self, model: str) -> ChatGPTStatus:
        credentials = self.store.load()
        if credentials is None or model not in credentials.models:
            raise ValueError("Selected model is not available for this ChatGPT account")
        self.store.save(credentials.model_copy(update={"selected_model": model}))
        return self.status()

    @staticmethod
    def _token_is_fresh(credentials: ChatGPTCredentials) -> bool:
        return bool(
            credentials.access_token
            and credentials.expires_at
            and credentials.expires_at > datetime.now(UTC) + timedelta(minutes=2)
        )

    def refresh_access_token(self) -> tuple[str, str]:
        with self._refresh_lock, self.store.session_lock():
            credentials = self.store.load()
            if (
                credentials is None
                or not credentials.plan_enabled
                or not credentials.access_token
                or not credentials.refresh_token
                or not credentials.client_id
                or not credentials.selected_model
            ):
                raise RuntimeError("ChatGPT plan is not connected")
            if self._token_is_fresh(credentials):
                return credentials.access_token, credentials.selected_model

            response = self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": credentials.client_id,
                    "refresh_token": credentials.refresh_token,
                    "resource": OPENAI_API_BASE,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("OAuth refresh response was not an object")
            refreshed = credentials.model_copy(
                update={
                    "access_token": _required_string(payload, "access_token"),
                    "refresh_token": payload.get("refresh_token")
                    if isinstance(payload.get("refresh_token"), str)
                    else credentials.refresh_token,
                    "scopes": _scopes_from(payload, credentials.scopes),
                    "expires_at": _expiry_from(payload),
                }
            )
            self.store.save(refreshed)
            return refreshed.access_token, refreshed.selected_model

    def inference_credentials(self) -> tuple[str, str] | None:
        credentials = self.store.load()
        if credentials is None or not credentials.plan_enabled:
            return None
        return self.refresh_access_token()

    def disconnect(self) -> ChatGPTStatus:
        credentials = self.store.load()
        if credentials is None or not credentials.refresh_token or not credentials.client_id:
            self.store.clear_session()
            return self.status()
        response = self._http.post(
            REVOCATION_URL,
            data={
                "client_id": credentials.client_id,
                "token": credentials.refresh_token,
                "token_type_hint": "refresh_token",
            },
        )
        if response.is_error:
            raise RuntimeError("Unable to disconnect ChatGPT; try again")
        self.store.clear_session()
        return self.status()
