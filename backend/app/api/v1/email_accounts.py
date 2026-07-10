import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.html_sanitize import sanitize_html
from app.dependencies import get_current_user
from app.integrations.email.manager import render_signature_html
from app.models.email_account import (
    EmailAccount,
    EmailHealthStatus,
    EmailProviderType,
    SignatureMode,
)
from app.models.user import User
from app.schemas.email import (
    EmailAccountCreate,
    EmailAccountResponse,
    EmailAccountUpdate,
    EmailAccountVerifyResponse,
    SendTestEmailRequest,
    SignaturePreviewRequest,
    SignaturePreviewResponse,
)

router = APIRouter()

_SIGNATURE_INPUT_FIELDS = {
    "signature_enabled",
    "signature_content",
    "signature_logo_attachment_id",
    "brand_color",
    "social_links",
}


def _logo_url(attachment_id: uuid.UUID | None) -> str | None:
    if not attachment_id:
        return None
    return f"{settings.base_url}/api/v1/uploads/public/{attachment_id}"


async def _get_account(db: AsyncSession, team_id: uuid.UUID, account_id: uuid.UUID) -> EmailAccount:
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.team_id == team_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundException("Email account not found")
    return account


def _sanitize_provider_config(provider_config: dict | None) -> dict | None:
    if not provider_config:
        return None
    return {
        key: value
        for key, value in provider_config.items()
        if value not in (None, "", [])
    }


@router.get("", response_model=list[EmailAccountResponse])
async def list_email_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EmailAccount)
        .where(EmailAccount.team_id == current_user.team_id)
        .order_by(EmailAccount.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=EmailAccountResponse, status_code=201)
async def create_email_account(
    data: EmailAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = EmailAccount(
        team_id=current_user.team_id,
        email_address=data.email_address,
        display_name=data.display_name,
        provider_type=EmailProviderType(data.provider_type),
        provider_config=_sanitize_provider_config(data.provider_config),
        daily_limit=data.daily_limit,
    )
    db.add(account)
    await db.flush()
    return account


@router.put("/{account_id}", response_model=EmailAccountResponse)
async def update_email_account(
    account_id: uuid.UUID,
    data: EmailAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(db, current_user.team_id, account_id)

    update_fields = data.model_dump(exclude_unset=True)
    effective_mode = update_fields.get("signature_mode", account.signature_mode.value)

    for field, value in update_fields.items():
        if field == "provider_config":
            value = _sanitize_provider_config(value)
        elif field == "signature_mode":
            value = SignatureMode(value)
        elif field == "signature_html":
            if effective_mode != SignatureMode.custom.value:
                # Structured mode owns signature_html via render_signature_html;
                # never store caller-supplied (unsanitized) HTML directly.
                continue
            # Custom mode: the caller's rich-text HTML is sanitized and stored
            # directly, bypassing render_signature_html's plain-text escaping.
            value = sanitize_html(value)
        setattr(account, field, value)

    # Structured mode (default): re-render the canonical signature HTML
    # whenever any structured input changed — or when the mode itself was
    # switched (back) to structured, so stale custom HTML can't linger.
    # Skipped entirely in custom mode so the freshly-sanitized signature_html
    # set above isn't clobbered.
    if effective_mode == SignatureMode.structured.value and (
        (_SIGNATURE_INPUT_FIELDS | {"signature_mode"}) & update_fields.keys()
    ):
        account.signature_html = render_signature_html(
            content=account.signature_content,
            logo_url=_logo_url(account.signature_logo_attachment_id),
            brand_color=account.brand_color,
            social_links=account.social_links,
        )

    await db.flush()
    return account


@router.post("/signature/preview", response_model=SignaturePreviewResponse)
async def preview_signature(
    data: SignaturePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return SignaturePreviewResponse(
        signature_html=render_signature_html(
            content=data.signature_content,
            logo_url=_logo_url(data.signature_logo_attachment_id),
            brand_color=data.brand_color,
            social_links=data.social_links,
        )
    )


@router.delete("/{account_id}", status_code=204)
async def delete_email_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(db, current_user.team_id, account_id)
    await db.delete(account)


@router.post("/{account_id}/test")
async def test_email_account(
    account_id: uuid.UUID,
    data: SendTestEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(db, current_user.team_id, account_id)

    # Send test email via the configured provider
    from app.integrations.email.manager import get_email_sender

    try:
        sender = get_email_sender(account)
        message_id = await sender.send(
            from_address=account.email_address,
            to_address=data.to_address,
            subject=data.subject,
            html_body=f"<p>{data.body}</p>",
            text_body=data.body,
        )
        account.health_status = EmailHealthStatus.healthy
        return {"success": True, "message_id": message_id}
    except Exception as e:
        account.health_status = EmailHealthStatus.degraded
        return {"success": False, "error": str(e)}


@router.post("/{account_id}/verify", response_model=EmailAccountVerifyResponse)
async def verify_email_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.integrations.email.manager import get_email_sender

    account = await _get_account(db, current_user.team_id, account_id)
    sender = get_email_sender(account)

    try:
        success = await sender.verify_connection()
        account.health_status = (
            EmailHealthStatus.healthy if success else EmailHealthStatus.degraded
        )
        await db.flush()
        return {
            "success": success,
            "health_status": account.health_status.value,
            "error": None if success else "Connection verification failed",
        }
    except Exception as exc:
        account.health_status = EmailHealthStatus.degraded
        await db.flush()
        return {
            "success": False,
            "health_status": account.health_status.value,
            "error": str(exc),
        }
