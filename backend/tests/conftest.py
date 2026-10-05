from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def isolate_chatgpt_credentials(monkeypatch, tmp_path):
    from app.chatgpt.deps import get_chatgpt_service
    from app.core.config import get_settings

    get_settings.cache_clear()
    get_chatgpt_service.cache_clear()
    monkeypatch.setenv(
        "TRIPWISE_CHATGPT_CREDENTIALS_PATH",
        str(tmp_path / "chatgpt-credentials.json"),
    )
    yield
    get_chatgpt_service.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    import app.models  # noqa: F401
    from app.db.database import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
