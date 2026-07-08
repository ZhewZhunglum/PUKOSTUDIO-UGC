import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies import get_current_user
from app.models.email_attachment import AttachmentPurpose, EmailAttachment
from app.models.user import User
from app.schemas.attachment import AttachmentResponse
from app.services import attachment_service

router = APIRouter()


@router.post("", response_model=AttachmentResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = Form("email"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        purpose_enum = AttachmentPurpose(purpose)
    except ValueError:
        raise BadRequestException(f"Invalid purpose: {purpose}")

    return await attachment_service.save_upload(
        db, current_user.team_id, current_user.id, file, purpose_enum
    )


_PUBLIC_ATTACHMENT_PURPOSES = [AttachmentPurpose.signature_logo, AttachmentPurpose.snippet_asset]


@router.get("/public/{attachment_id}")
async def serve_public_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Unauthenticated serve for inline email images (signature logos + rich-text
    editor images embedded in template/reply bodies via the snippet_asset purpose).

    Both are embedded as <img src> in outbound emails, so recipient mail clients
    must fetch them without auth. Access is guarded by the unguessable UUID and
    restricted to these two purposes; sensitive email attachments (purpose
    "email") are NOT served here (use the authed route below).
    """
    result = await db.execute(
        select(EmailAttachment).where(
            EmailAttachment.id == attachment_id,
            EmailAttachment.purpose.in_(_PUBLIC_ATTACHMENT_PURPOSES),
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise NotFoundException("Image not found")
    return FileResponse(
        attachment_service.attachment_path(attachment),
        media_type=attachment.content_type,
    )


@router.get("/{attachment_id}")
async def download_file(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attachment = await attachment_service.get_attachment(
        db, attachment_id, current_user.team_id
    )
    return FileResponse(
        attachment_service.attachment_path(attachment),
        media_type=attachment.content_type,
        filename=attachment.filename,
    )
