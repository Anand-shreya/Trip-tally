from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_options(url: str) -> dict:
    return {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, **_engine_options(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def init_db() -> None:
    import app.models  # noqa: F401
    from app.models import User

    Base.metadata.create_all(engine)
    with SessionLocal.begin() as session:
        if session.get(User, settings.demo_user_id) is None:
            session.add(
                User(
                    id=settings.demo_user_id,
                    name=settings.demo_user_name,
                    email=settings.demo_user_email,
                )
            )

