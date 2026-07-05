import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

_sync_engine = None
_SyncSessionLocal = None


def get_sync_session():
    """Return a synchronous database session for Celery tasks.

    Reuses a single module-level Engine (and its connection pool) instead of
    creating a fresh Engine on every call. Creating a new Engine per task never
    disposed the previous one, leaking a connection pool each time a task ran.
    """
    global _sync_engine, _SyncSessionLocal
    if _SyncSessionLocal is None:
        _sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
        _SyncSessionLocal = sessionmaker(bind=_sync_engine)
    return _SyncSessionLocal()


def ai_is_configured() -> bool:
    if settings.ai_provider == "claude":
        return bool(settings.claude_api_key)
    if settings.ai_provider == "openai":
        return bool(settings.openai_api_key)
    return False


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", " ", value).replace("\n", " ").strip()


def build_ai_thread(messages: list) -> list[dict]:
    return [
        {
            "from": message.from_address,
            "date": message.created_at.isoformat(),
            "body": message.body_text or strip_html(message.body_html),
        }
        for message in sorted(messages, key=lambda m: m.created_at)
    ]
