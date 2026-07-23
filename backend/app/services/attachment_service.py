import logging
import os
import re
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.email_attachment import AttachmentPurpose, EmailAttachment

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024

# Whitelisted content-type -> file extension. The on-disk name derives its
# extension from THIS map, never from the client-supplied filename.
_EXT_BY_CONTENT_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/zip": ".zip",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def _storage_root() -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    return settings.upload_dir


def _sanitize_filename(name: str | None) -> str:
    """Strip CR/LF and path separators, collapse whitespace, truncate to 255."""
    candidate = (name or "file").strip()
    candidate = candidate.replace("\r", "").replace("\n", "")
    candidate = candidate.replace("/", "_").replace("\\", "_")
    candidate = re.sub(r"\s+", " ", candidate)
    candidate = candidate.strip(". ") or "file"
    return candidate[:255]


def _abs_path(storage_key: str) -> str:
    # os.path.basename defends against traversal even if storage_key were tampered.
    return os.path.join(_storage_root(), os.path.basename(storage_key))


async def save_upload(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID | None,
    upload: UploadFile,
    purpose: AttachmentPurpose = AttachmentPurpose.email,
) -> EmailAttachment:
    content_type = (upload.content_type or "").lower().split(";")[0].strip()
    if content_type not in settings.upload_allowed_content_types:
        raise BadRequestException(f"Unsupported file type: {content_type or 'unknown'}")

    ext = _EXT_BY_CONTENT_TYPE.get(content_type, "")
    storage_key = f"{uuid.uuid4().hex}{ext}"
    dest = _abs_path(storage_key)

    size = 0
    try:
        with open(dest, "wb") as fh:
            while True:
                chunk = await upload.read(_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.upload_max_bytes:
                    raise BadRequestException(
                        f"File exceeds maximum size of {settings.upload_max_bytes} bytes"
                    )
                fh.write(chunk)
    except BadRequestException:
        if os.path.exists(dest):
            os.remove(dest)
        raise
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        logger.exception("Failed to persist upload")
        raise

    attachment = EmailAttachment(
        team_id=team_id,
        uploaded_by=user_id,
        filename=_sanitize_filename(upload.filename),
        content_type=content_type,
        size_bytes=size,
        storage_key=storage_key,
        purpose=purpose,
    )
    db.add(attachment)
    await db.flush()
    return attachment


async def get_attachment(
    db: AsyncSession, attachment_id: uuid.UUID, team_id: uuid.UUID
) -> EmailAttachment:
    result = await db.execute(
        select(EmailAttachment).where(
            EmailAttachment.id == attachment_id,
            EmailAttachment.team_id == team_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise NotFoundException("Attachment not found")
    return attachment


def attachment_path(attachment: EmailAttachment) -> str:
    return _abs_path(attachment.storage_key)


def load_attachment_payload(attachment: EmailAttachment) -> dict:
    """Read an attachment from disk into the dict shape the senders expect."""
    with open(_abs_path(attachment.storage_key), "rb") as fh:
        content_bytes = fh.read()
    return {
        "filename": attachment.filename,
        "content_bytes": content_bytes,
        "content_type": attachment.content_type,
    }


def _attachment_ids_query(team_id: uuid.UUID, attachment_ids: list[uuid.UUID]):
    """Team-scoped id-list SELECT, shared by the async and sync fetch paths so
    there's exactly one filter to test and keep in sync."""
    return select(EmailAttachment).where(
        EmailAttachment.id.in_(attachment_ids),
        EmailAttachment.team_id == team_id,
    )


async def attachment_payloads_for_ids(
    db: AsyncSession, team_id: uuid.UUID, attachment_ids: list[uuid.UUID]
) -> tuple[list[dict], list[EmailAttachment]]:
    """Team-scoped batch load. Returns (sender payloads, attachment rows)."""
    if not attachment_ids:
        return [], []
    result = await db.execute(_attachment_ids_query(team_id, attachment_ids))
    rows = list(result.scalars().all())
    payloads = [load_attachment_payload(a) for a in rows]
    return payloads, rows


def attachment_payloads_for_ids_sync(
    db: Session, team_id: uuid.UUID, attachment_ids: list[uuid.UUID]
) -> list[dict]:
    """Sync-session twin of ``attachment_payloads_for_ids``, for Celery workers
    (``email_tasks.py``/``client_email_tasks.py`` use a sync ``Session``, not
    an ``AsyncSession``). Same team-scoped filter, same payload shape."""
    if not attachment_ids:
        return []
    rows = db.execute(_attachment_ids_query(team_id, attachment_ids)).scalars().all()
    return [load_attachment_payload(a) for a in rows]
