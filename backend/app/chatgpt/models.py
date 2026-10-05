from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

DIRECT_TOKEN_SCOPE = "chatgpt.tokens.use.direct"
MANAGE_USAGE_URL = "https://chatgpt.com/settings/usage"


class ChatGPTCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    @field_validator("host_id")
    @classmethod
    def validate_host_id(cls, value: str) -> str:
        prefix = "urn:uuid:"
        if not value.startswith(prefix):
            raise ValueError("host_id must be an opaque urn:uuid identifier")
        UUID(value.removeprefix(prefix))
        return value

    @field_validator("client_id")
    @classmethod
    def reject_registration_placeholder(cls, value: str | None) -> str | None:
        if value == "dynamic_agent_client":
            raise ValueError("dynamic_agent_client cannot be persisted as an issued client ID")
        return value

    @property
    def signed_in(self) -> bool:
        return bool(self.client_id and self.subject and self.id_token)

    @property
    def plan_enabled(self) -> bool:
        return bool(
            self.signed_in
            and DIRECT_TOKEN_SCOPE in self.scopes
            and self.access_token
            and self.refresh_token
            and self.selected_model
        )


class ChatGPTStatus(BaseModel):
    state: Literal["disconnected", "connected", "scope_required"]
    signed_in: bool
    plan_enabled: bool
    name: str | None = None
    email: str | None = None
    models: list[str] = Field(default_factory=list)
    selected_model: str | None = None
    manage_usage_url: str = MANAGE_USAGE_URL


class ChatGPTModelSelection(BaseModel):
    model: str = Field(min_length=1, max_length=200)
