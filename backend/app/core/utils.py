import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


def get_sync_session():
    """Create a synchronous database session for Celery tasks."""
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


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
