from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TripWise API"
    environment: str = "development"
    debug: bool = False
    database_url: str = "sqlite+pysqlite:///./tripwise.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"
    demo_user_name: str = "TripWise Explorer"
    demo_user_email: str = "explorer@tripwise.local"
    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    chatgpt_credentials_path: str = ".tripwise/chatgpt-credentials.json"
    chatgpt_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/chatgpt/callback"
    frontend_url: str = "http://localhost:5173"
    weather_provider: str = "local"
    openweather_api_key: str | None = None
    queue_mode: str = "inline"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRIPWISE_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
