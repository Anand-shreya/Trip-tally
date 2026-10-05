from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/ai", tags=["ai"])


class AIProviderStatus(BaseModel):
    provider: Literal["gemini", "local"]
    label: str
    model: str | None
    ai_enabled: bool


@router.get("/status", response_model=AIProviderStatus)
def ai_provider_status() -> AIProviderStatus:
    settings = get_settings()
    if settings.gemini_enabled and settings.gemini_api_key:
        return AIProviderStatus(
            provider="gemini",
            label="Gemini free tier",
            model=settings.gemini_model,
            ai_enabled=True,
        )
    return AIProviderStatus(
        provider="local",
        label="Local planning",
        model=None,
        ai_enabled=False,
    )
