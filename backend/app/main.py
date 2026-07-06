import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_SECRET_KEY = "change-me-to-a-random-string-in-production"


def _validate_runtime_config() -> None:
    """Fail fast on insecure production config.

    A default SECRET_KEY lets anyone forge JWTs (and thus impersonate any team),
    so refuse to boot with it outside development. In development we only warn.
    """
    if settings.secret_key == _DEFAULT_SECRET_KEY:
        if settings.app_env == "development":
            logger.warning(
                "SECRET_KEY is the built-in default; set a strong SECRET_KEY before deploying."
            )
        else:
            raise RuntimeError(
                "SECRET_KEY is still the built-in default in a non-development "
                "environment. Set a strong, random SECRET_KEY before starting."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _validate_runtime_config()
    yield
    # Shutdown
    from app.core.database import engine

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    from redis import Redis

    from app.core.database import engine
    from app.workers.celery_app import celery_app

    checks: dict[str, dict[str, str | int | None]] = {
        "app": {"status": "ok"},
        "db": {"status": "error", "detail": None},
        "redis": {"status": "error", "detail": None},
        "worker": {"status": "error", "detail": None},
    }

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["db"] = {"status": "ok", "detail": None}
    except Exception as exc:  # pragma: no cover - exercised by runtime environment
        checks["db"] = {"status": "error", "detail": str(exc)}

    try:
        redis_client = Redis.from_url(settings.redis_url)
        redis_client.ping()
        checks["redis"] = {"status": "ok", "detail": None}
    except Exception as exc:  # pragma: no cover - exercised by runtime environment
        checks["redis"] = {"status": "error", "detail": str(exc)}

    try:
        ping_response = celery_app.control.ping(timeout=1)
        if ping_response:
            checks["worker"] = {"status": "ok", "detail": None}
        else:
            checks["worker"] = {"status": "degraded", "detail": "No active worker responded"}
    except Exception as exc:  # pragma: no cover - exercised by runtime environment
        checks["worker"] = {"status": "error", "detail": str(exc)}

    overall_status = (
        "ok"
        if all(check["status"] == "ok" for check in checks.values())
        else "degraded"
    )
    return {"status": overall_status, "checks": checks}
