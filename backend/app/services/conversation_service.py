import uuid
from datetime import datetime, timezone
from email.utils import getaddresses

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.utils import strip_html
from app.integrations.email.manager import (
    apply_signature,
    get_email_sender,
    select_best_account,
)
from app.models.ai import AIDraftStatus, AIMessageDraft
from app.models.campaign import CampaignInfluencer, CampaignInfluencerStatus
from app.models.conversation import AIIntent, Conversation
from app.models.email_account import EmailAccount
from app.models.email_message import EmailDirection, EmailMessage, EmailStatus
from app.models.influencer import Influencer, InfluencerStatus
from app.schemas.conversation import SendReplyRequest


def _message_preview(message: EmailMessage | None) -> str | None:
    if not message:
        return None
    body = message.body_text or strip_html(message.body_html)
    return body[:160] if body else None


def _reply_subject(subject: str | None) -> str:
    base_subject = (subject or "Hello").strip()
    if base_subject.lower().startswith("re:"):
        return base_subject
    return f"Re: {base_subject}"


def _normalize_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [address for _, address in getaddresses([value]) if address]


async def _get_conversation_row(
    db: AsyncSession, conversation_id: uuid.UUID, team_id: uuid.UUID
) -> tuple[Conversation, Influencer]:
    result = await db.execute(
        select(Conversation, Influencer)
        .join(Influencer, Influencer.id == Conversation.influencer_id)
        .where(Conversation.id == conversation_id, Conversation.team_id == team_id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundException("Conversation not found")
    return row


async def _apply_intent_mapping(
    db: AsyncSession, conversation: Conversation, influencer: Influencer, ai_intent: AIIntent
) -> None:
    campaign_status: CampaignInfluencerStatus | None = None

    if ai_intent in {AIIntent.interested, AIIntent.question, AIIntent.negotiation}:
        influencer.status = InfluencerStatus.replied
        campaign_status = CampaignInfluencerStatus.replied
    elif ai_intent == AIIntent.not_interested:
        influencer.status = InfluencerStatus.rejected
        campaign_status = CampaignInfluencerStatus.completed
    elif ai_intent == AIIntent.spam:
        influencer.status = InfluencerStatus.blacklisted
        campaign_status = CampaignInfluencerStatus.unsubscribed

    if not campaign_status:
        return

    enrollments = await db.execute(
        select(CampaignInfluencer).where(CampaignInfluencer.influencer_id == conversation.influencer_id)
    )
    for enrollment in enrollments.scalars().all():
        enrollment.status = campaign_status


async def list_conversations(
    db: AsyncSession, team_id: uuid.UUID, bucket: str = "all"
) -> list[dict]:
    latest_message_subquery = (
        select(
            EmailMessage.influencer_id.label("influencer_id"),
            func.max(EmailMessage.created_at).label("latest_created_at"),
        )
        .where(EmailMessage.team_id == team_id)
        .group_by(EmailMessage.influencer_id)
        .subquery()
    )

    query = (
        select(Conversation, Influencer, EmailMessage)
        .join(Influencer, Influencer.id == Conversation.influencer_id)
        .outerjoin(
            latest_message_subquery,
            latest_message_subquery.c.influencer_id == Conversation.influencer_id,
        )
        .outerjoin(
            EmailMessage,
            and_(
                EmailMessage.influencer_id == Conversation.influencer_id,
                EmailMessage.created_at == latest_message_subquery.c.latest_created_at,
            ),
        )
        .where(Conversation.team_id == team_id)
        .order_by(Conversation.last_message_at.desc().nullslast())
    )

    if bucket == "needs_review":
        query = query.where(Conversation.needs_review.is_(True))
    elif bucket == "assigned":
        query = query.where(Conversation.assigned_to.is_not(None))
    elif bucket == "replied":
        query = query.where(Conversation.unread_count == 0)
    elif bucket == "has_draft":
        query = query.where(
            select(AIMessageDraft.id)
            .where(
                AIMessageDraft.conversation_id == Conversation.id,
                AIMessageDraft.status == AIDraftStatus.pending_review,
            )
            .exists()
        )
    elif bucket == "negotiation":
        query = query.where(Conversation.ai_intent == AIIntent.negotiation)
    elif bucket == "blacklisted":
        query = query.where(Influencer.status == InfluencerStatus.blacklisted)

    rows = (await db.execute(query)).all()
    conversation_ids = [conversation.id for conversation, _, _ in rows]
    latest_drafts: dict[uuid.UUID, AIMessageDraft] = {}
    if conversation_ids:
        draft_result = await db.execute(
            select(AIMessageDraft)
            .where(AIMessageDraft.conversation_id.in_(conversation_ids))
            .distinct(AIMessageDraft.conversation_id)
            .order_by(AIMessageDraft.conversation_id, AIMessageDraft.created_at.desc())
        )
        latest_drafts = {
            draft.conversation_id: draft for draft in draft_result.scalars().all()
        }

    items: list[dict] = []
    for conversation, influencer, latest_message in rows:
        latest_draft = latest_drafts.get(conversation.id)
        items.append(
            {
                "id": conversation.id,
                "influencer_id": influencer.id,
                "influencer_name": influencer.name,
                "influencer_email": influencer.email,
                "last_message_at": conversation.last_message_at,
                "unread_count": conversation.unread_count,
                "ai_intent": conversation.ai_intent.value if conversation.ai_intent else None,
                "ai_confidence": conversation.ai_confidence,
                "needs_review": conversation.needs_review,
                "assigned_to": conversation.assigned_to,
                "latest_subject": latest_message.subject if latest_message else None,
                "last_message_preview": _message_preview(latest_message),
                "latest_draft_id": latest_draft.id if latest_draft else None,
                "latest_draft_status": latest_draft.status.value if latest_draft else None,
                "risk_level": latest_draft.risk_level.value if latest_draft else None,
                "automation_status": (
                    "draft_ready"
                    if latest_draft and latest_draft.status == AIDraftStatus.pending_review
                    else "needs_playbook"
                    if latest_draft and latest_draft.status == AIDraftStatus.failed
                    else "manual"
                ),
            }
        )
    return items


async def get_conversation_detail(
    db: AsyncSession, conversation_id: uuid.UUID, team_id: uuid.UUID
) -> dict:
    conversation, influencer = await _get_conversation_row(db, conversation_id, team_id)

    message_result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == team_id,
            EmailMessage.influencer_id == conversation.influencer_id,
        )
        .order_by(EmailMessage.created_at.asc())
    )
    messages = list(message_result.scalars().all())
    latest_message = messages[-1] if messages else None
    latest_draft = (
        await db.execute(
            select(AIMessageDraft)
            .where(
                AIMessageDraft.team_id == team_id,
                AIMessageDraft.conversation_id == conversation_id,
            )
            .order_by(AIMessageDraft.created_at.desc())
        )
    ).scalars().first()

    return {
        "id": conversation.id,
        "influencer_id": influencer.id,
        "influencer_name": influencer.name,
        "influencer_email": influencer.email,
        "last_message_at": conversation.last_message_at,
        "unread_count": conversation.unread_count,
        "ai_intent": conversation.ai_intent.value if conversation.ai_intent else None,
        "ai_confidence": conversation.ai_confidence,
        "needs_review": conversation.needs_review,
        "assigned_to": conversation.assigned_to,
        "latest_subject": latest_message.subject if latest_message else None,
        "last_message_preview": _message_preview(latest_message),
        "latest_draft_id": latest_draft.id if latest_draft else None,
        "latest_draft_status": latest_draft.status.value if latest_draft else None,
        "risk_level": latest_draft.risk_level.value if latest_draft else None,
        "automation_status": (
            "draft_ready"
            if latest_draft and latest_draft.status == AIDraftStatus.pending_review
            else "needs_playbook"
            if latest_draft and latest_draft.status == AIDraftStatus.failed
            else "manual"
        ),
        "messages": [
            {
                "id": message.id,
                "direction": message.direction.value,
                "from_address": message.from_address,
                "to_address": message.to_address,
                "subject": message.subject,
                "body_html": message.body_html,
                "body_text": message.body_text,
                "status": message.status.value,
                "message_id": message.message_id,
                "in_reply_to": message.in_reply_to,
                "references": message.references,
                "sent_at": message.sent_at,
                "created_at": message.created_at,
            }
            for message in messages
        ],
    }


async def update_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: dict,
) -> dict:
    conversation, influencer = await _get_conversation_row(db, conversation_id, team_id)

    if "needs_review" in payload and payload["needs_review"] is not None:
        conversation.needs_review = payload["needs_review"]
    if "assigned_to" in payload:
        conversation.assigned_to = payload["assigned_to"]

    if payload.get("ai_intent"):
        try:
            ai_intent = AIIntent(payload["ai_intent"])
        except ValueError as exc:
            raise BadRequestException("Unsupported AI intent") from exc
        conversation.ai_intent = ai_intent
        conversation.ai_confidence = 1.0
        await _apply_intent_mapping(db, conversation, influencer, ai_intent)

    await db.flush()
    return await get_conversation_detail(db, conversation_id, team_id)


async def draft_reply(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    team_id: uuid.UUID,
    guidelines: str = "",
) -> AIMessageDraft:
    from app.services import ai_communication_service

    return await ai_communication_service.create_ai_draft(
        db, conversation_id, team_id, guidelines=guidelines
    )


async def send_reply(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: SendReplyRequest,
) -> dict:
    conversation, influencer = await _get_conversation_row(db, conversation_id, team_id)
    if not influencer.email:
        raise BadRequestException("Influencer does not have an email address")

    account: EmailAccount | None = None
    if payload.email_account_id:
        account_result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.id == payload.email_account_id,
                EmailAccount.team_id == team_id,
                EmailAccount.is_active.is_(True),
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            raise NotFoundException("Email account not found")
    else:
        accounts_result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.team_id == team_id,
                EmailAccount.is_active.is_(True),
            )
        )
        account = select_best_account(list(accounts_result.scalars().all()), influencer.email.split("@")[-1])
        if not account:
            raise BadRequestException("No available sending account")

    message_result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == team_id,
            EmailMessage.influencer_id == influencer.id,
        )
        .order_by(EmailMessage.created_at.asc())
    )
    history = list(message_result.scalars().all())
    latest_message = history[-1] if history else None
    latest_campaign_id = latest_message.campaign_id if latest_message else None
    reference_ids = [message.message_id for message in history if message.message_id]

    subject = payload.subject or _reply_subject(latest_message.subject if latest_message else None)
    body_text = payload.body_text or strip_html(payload.body_html)

    headers: dict[str, str] | None = None
    if reference_ids:
        headers = {
            "In-Reply-To": reference_ids[-1],
            "References": " ".join(reference_ids[-5:]),
        }

    from app.services import attachment_service

    attachment_payloads, attachment_rows = await attachment_service.attachment_payloads_for_ids(
        db, team_id, payload.attachment_ids
    )

    signed_html, signed_text = apply_signature(payload.body_html, body_text, account)

    sender = get_email_sender(account)
    message = EmailMessage(
        team_id=team_id,
        campaign_id=latest_campaign_id,
        campaign_step_id=None,
        influencer_id=influencer.id,
        email_account_id=account.id,
        direction=EmailDirection.outbound,
        from_address=account.email_address,
        to_address=influencer.email,
        subject=subject,
        body_html=signed_html,
        body_text=signed_text,
        status=EmailStatus.sending,
        in_reply_to=reference_ids[-1] if reference_ids else None,
        references=headers["References"] if headers else None,
    )
    db.add(message)
    await db.flush()

    message_id = await sender.send(
        from_address=f"{account.display_name or 'Team'} <{account.email_address}>",
        to_address=influencer.email,
        subject=subject,
        html_body=signed_html,
        text_body=signed_text,
        headers=headers,
        attachments=attachment_payloads or None,
    )

    message.message_id = message_id
    message.status = EmailStatus.sent
    message.sent_at = datetime.now(timezone.utc)
    for attachment in attachment_rows:
        attachment.email_message_id = message.id
    account.sent_today += 1
    conversation.unread_count = 0
    conversation.needs_review = False
    await db.flush()

    return await get_conversation_detail(db, conversation_id, team_id)


async def ingest_inbound_email(db: AsyncSession, payload: dict) -> dict:
    from_addresses = _normalize_addresses(payload.get("from") or payload.get("sender"))
    to_addresses = _normalize_addresses(payload.get("to"))
    if not from_addresses or not to_addresses:
        raise BadRequestException("Inbound payload must include valid from/to addresses")

    from_email = from_addresses[0]
    to_email = to_addresses[0]
    raw_message_id = (
        payload.get("message_id")
        or payload.get("Message-Id")
        or payload.get("message-id")
    )
    subject = payload.get("subject") or "(no subject)"
    body_text = payload.get("text") or payload.get("body-plain") or payload.get("body") or ""
    body_html = payload.get("html") or payload.get("body-html") or ""
    in_reply_to = payload.get("in_reply_to") or payload.get("In-Reply-To")
    references = payload.get("references") or payload.get("References")

    account_result = await db.execute(
        select(EmailAccount).where(EmailAccount.email_address == to_email)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise NotFoundException("Inbound recipient account not found")

    influencer_result = await db.execute(
        select(Influencer).where(
            Influencer.team_id == account.team_id,
            Influencer.email == from_email,
        )
    )
    influencer = influencer_result.scalar_one_or_none()
    if not influencer:
        raise NotFoundException("Inbound sender is not a known influencer")

    existing_message = None
    if raw_message_id:
        existing_result = await db.execute(
            select(EmailMessage).where(
                EmailMessage.team_id == account.team_id,
                EmailMessage.message_id == raw_message_id,
            )
        )
        existing_message = existing_result.scalar_one_or_none()
    if existing_message:
        return {"conversation_id": None, "created": False}

    related_message = None
    reference_candidates = [value for value in [in_reply_to, references] if value]
    if reference_candidates:
        related_result = await db.execute(
            select(EmailMessage)
            .where(
                EmailMessage.team_id == account.team_id,
                or_(
                    EmailMessage.message_id == in_reply_to,
                    EmailMessage.message_id.in_(
                        [candidate.strip() for candidate in str(references or "").split() if candidate.strip()]
                    ),
                ),
            )
            .order_by(EmailMessage.created_at.desc())
        )
        related_message = related_result.scalars().first()

    message = EmailMessage(
        team_id=account.team_id,
        campaign_id=related_message.campaign_id if related_message else None,
        campaign_step_id=related_message.campaign_step_id if related_message else None,
        influencer_id=influencer.id,
        email_account_id=account.id,
        direction=EmailDirection.inbound,
        from_address=from_email,
        to_address=to_email,
        subject=subject,
        body_html=body_html or None,
        body_text=body_text or None,
        message_id=raw_message_id,
        in_reply_to=in_reply_to,
        references=references,
        status=EmailStatus.delivered,
        metadata_=payload,
    )
    db.add(message)
    await db.flush()

    conversation_result = await db.execute(
        select(Conversation).where(
            Conversation.team_id == account.team_id,
            Conversation.influencer_id == influencer.id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if not conversation:
        conversation = Conversation(
            team_id=account.team_id,
            influencer_id=influencer.id,
            last_message_at=message.created_at,
            unread_count=1,
            needs_review=True,
        )
        db.add(conversation)
    else:
        conversation.last_message_at = message.created_at
        conversation.unread_count += 1
        conversation.needs_review = True

    await db.flush()
    return {"conversation_id": conversation.id, "created": True}
