"""Suppression list: addresses the team must not email.

Populated on hard bounce / complaint / unsubscribe (and manually). Sends consult
this list first. Provides both async (API / async services) and sync (Celery
worker) variants.
"""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.suppression import EmailSuppression, SuppressionReason

_CONSTRAINT = "uq_email_suppressions_team_email"


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _insert_stmt(team_id: uuid.UUID, email: str, reason: SuppressionReason | str):
    reason_value = reason.value if isinstance(reason, SuppressionReason) else reason
    # Explicit id: the ORM's uuid4 default is not applied to a core insert.
    # on_conflict_do_nothing makes re-suppressing an existing address a no-op
    # (never raises, so it is safe to call mid-transaction).
    return (
        pg_insert(EmailSuppression)
        .values(id=uuid.uuid4(), team_id=team_id, email=email, reason=reason_value)
        .on_conflict_do_nothing(constraint=_CONSTRAINT)
    )


# ── async (API + async services) ────────────────────────────────────────────
async def is_suppressed(db: AsyncSession, team_id: uuid.UUID, email: str | None) -> bool:
    e = normalize_email(email)
    if not e:
        return False
    result = await db.execute(
        select(EmailSuppression.id).where(
            EmailSuppression.team_id == team_id, EmailSuppression.email == e
        )
    )
    return result.first() is not None


async def add_suppression(
    db: AsyncSession, team_id: uuid.UUID, email: str | None, reason: SuppressionReason
) -> None:
    e = normalize_email(email)
    if not e:
        return
    await db.execute(_insert_stmt(team_id, e, reason))


async def list_suppressions(db: AsyncSession, team_id: uuid.UUID) -> list[EmailSuppression]:
    result = await db.execute(
        select(EmailSuppression)
        .where(EmailSuppression.team_id == team_id)
        .order_by(EmailSuppression.created_at.desc())
    )
    return list(result.scalars().all())


async def remove_suppression(
    db: AsyncSession, team_id: uuid.UUID, suppression_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(EmailSuppression).where(
            EmailSuppression.id == suppression_id, EmailSuppression.team_id == team_id
        )
    )
    return (result.rowcount or 0) > 0


# ── sync (Celery worker) ─────────────────────────────────────────────────────
def is_suppressed_sync(db: Session, team_id: uuid.UUID, email: str | None) -> bool:
    e = normalize_email(email)
    if not e:
        return False
    return (
        db.execute(
            select(EmailSuppression.id).where(
                EmailSuppression.team_id == team_id, EmailSuppression.email == e
            )
        ).first()
        is not None
    )


def add_suppression_sync(
    db: Session, team_id: uuid.UUID, email: str | None, reason: SuppressionReason
) -> None:
    e = normalize_email(email)
    if not e:
        return
    db.execute(_insert_stmt(team_id, e, reason))
