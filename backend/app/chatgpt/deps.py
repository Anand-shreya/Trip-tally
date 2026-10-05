from functools import lru_cache

from app.chatgpt.service import ChatGPTService
from app.chatgpt.store import CredentialStore
from app.core.config import get_settings


@lru_cache
def get_chatgpt_service() -> ChatGPTService:
    settings = get_settings()
    return ChatGPTService(
        store=CredentialStore(settings.chatgpt_credentials_path),
        redirect_uri=settings.chatgpt_redirect_uri,
    )
