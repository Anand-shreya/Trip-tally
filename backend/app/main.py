from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import get_settings
from app.core.exceptions import TripWiseError
from app.db.database import init_db


def create_app(*, init_database: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if init_database:
            init_db()
        yield

    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Travel planning, shared expenses, and exact settlements.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(TripWiseError)
    async def tripwise_error_handler(_: Request, exc: TripWiseError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @application.get("/api/v1/health", tags=["health"])
    def health():
        return {"status": "ok", "service": "tripwise-api"}

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
