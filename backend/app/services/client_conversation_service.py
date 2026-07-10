import uuid
from datetime import datetime, timezone
from email.utils import getaddresses

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.html_sanitize import sanitize_html
from app.core.utils import strip_html
from app.integrations.email.manager import (
    apply_signature,
    finalize_html_for_send,
    get_email_sender,
    select_best_account,
)
from app.models.client import Client, ClientStatus
from app.models.client_campaign import (
    ClientCampaignEnrollment,
    ClientCampaignInfluencerStatus,
)
from app.models.client_conversation import ClientConversation
from app.models.client_email_message import (
    ClientEmailDirection,
    ClientEmailMessage,
    ClientEmailStatus,
)
from app.models.email_account import EmailAccount
from app.schemas.client_conversation import SendClientReplyRequest


def _message_preview(message: ClientEmailMessage | None) -> str | None:
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
) -> tuple[ClientConversation, Client]:
    result = await db.execute(
        select(ClientConversation, Client)
        .join(Client, Client.id == ClientConversation.client_id)
        .where(ClientConversation.id == conversation_id, ClientConversation.team_id == team_id)
    )
    row = result.one_or_none()
    if not row:
        raise NotFoundException("Conversation not found")
    return row


async def list_conversations(
    db: AsyncSession, team_id: uuid.UUID, bucket: str = "all"
) -> list[dict]:
    latest_message_subquery = (
        select(
            ClientEmailMessage.client_id.label("client_id"),
            func.max(ClientEmailMessage.created_at).label("latest_created_at"),
        )
        .where(ClientEmailMessage.team_id == team_id)
        .group_by(ClientEmailMessage.client_id)
        .subquery()
    )

    query = (
        select(ClientConversation, Client, ClientEmailMessage)
        .join(Client, Client.id == ClientConversation.client_id)
        .outerjoin(
            latest_message_subquery,
            latest_message_subquery.c.client_id == ClientConversation.client_id,
        )
        .outerjoin(
            ClientEmailMessage,
            and_(
                ClientEmailMessage.client_id == ClientConversation.client_id,
                ClientEmailMessage.created_at == latest_message_subquery.c.latest_created_at,
            ),
        )
        .where(ClientConversation.team_id == team_id)
        .order_by(ClientConversation.last_message_at.desc().nullslast())
    )

    if bucket == "needs_review":
        query = query.where(ClientConversation.needs_review.is_(True))
    elif bucket == "assigned":
        query = query.where(ClientConversation.assigned_to.is_not(None))
    elif bucket == "replied":
        query = query.where(ClientConversation.unread_count == 0)

    rows = (await db.execute(query)).all()

    items: list[dict] = []
    for conversation, client, latest_message in rows:
        items.append(
            {
                "id": conversation.id,
                "client_id": client.id,
                "client_company_name": client.company_name,
                "client_email": client.email,
                "last_message_at": conversation.last_message_at,
                "unread_count": conversation.unread_count,
                "needs_review": conversation.needs_review,
                "assigned_to": conversation.assigned_to,
                "latest_subject": latest_message.subject if latest_message else None,
                "last_message_preview": _message_preview(latest_message),
            }
        )
    return items


async def get_conversation_detail(
    db: AsyncSession, conversation_id: uuid.UUID, team_id: uuid.UUID
) -> dict:
    conversation, client = await _get_conversation_row(db, conversation_id, team_id)

    message_result = await db.execute(
        select(ClientEmailMessage)
        .where(
            ClientEmailMessage.team_id == team_id,
            ClientEmailMessage.client_id == conversation.client_id,
        )
        .order_by(ClientEmailMessage.created_at.asc())
    )
    messages = list(message_result.scalars().all())
    latest_message = messages[-1] if messages else None

    return {
        "id": conversation.id,
        "client_id": client.id,
        "client_company_name": client.company_name,
        "client_email": client.email,
        "last_message_at": conversation.last_message_at,
        "unread_count": conversation.unread_count,
        "needs_review": conversation.needs_review,
        "assigned_to": conversation.assigned_to,
        "latest_subject": latest_message.subject if latest_message else None,
        "last_message_preview": _message_preview(latest_message),
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
    conversation, _client = await _get_conversation_row(db, conversation_id, team_id)

    if "needs_review" in payload and payload["needs_review"] is not None:
        conversation.needs_review = payload["needs_review"]
    if "assigned_to" in payload:
        conversation.assigned_to = payload["assigned_to"]

    await db.flush()
    return await get_conversation_detail(db, conversation_id, team_id)


async def send_reply(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: SendClientReplyRequest,
) -> dict:
    conversation, client = await _get_conversation_row(db, conversation_id, team_id)
    if not client.email:
        raise BadRequestException("Client does not have an email address")

    from app.services import suppression_service

    if await suppression_service.is_suppressed(db, team_id, client.email):
        raise BadRequestException(
            "该收件人在抑制名单中（曾退信/投诉/退订），已阻止发送。"
            "如确认无误，可在设置中将其移出抑制名单后重试。"
        )

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
        if account.sent_today >= account.daily_limit:
            raise BadRequestException("Selected sending account has reached its daily limit")
    else:
        accounts_result = await db.execute(
            select(EmailAccount).where(
                EmailAccount.team_id == team_id,
                EmailAccount.is_active.is_(True),
            )
        )
        account = select_best_account(list(accounts_result.scalars().all()), client.email.split("@")[-1])
        if not account:
            raise BadRequestException("No available sending account")

    message_result = await db.execute(
        select(ClientEmailMessage)
        .where(
            ClientEmailMessage.team_id == team_id,
            ClientEmailMessage.client_id == client.id,
        )
        .order_by(ClientEmailMessage.created_at.asc())
    )
    history = list(message_result.scalars().all())
    latest_message = history[-1] if history else None
    latest_campaign_id = latest_message.campaign_id if latest_message else None
    reference_ids = [message.message_id for message in history if message.message_id]

    subject = payload.subject or _reply_subject(latest_message.subject if latest_message else None)
    body_html = sanitize_html(payload.body_html)
    body_text = payload.body_text or strip_html(body_html)

    headers: dict[str, str] | None = None
    if reference_ids:
        headers = {
            "In-Reply-To": reference_ids[-1],
            "References": " ".join(reference_ids[-5:]),
        }

    signed_html, signed_text = apply_signature(body_html, body_text, account)
    final_html = finalize_html_for_send(signed_html)

    sender = get_email_sender(account)
    message = ClientEmailMessage(
        team_id=team_id,
        campaign_id=latest_campaign_id,
        campaign_step_id=None,
        client_id=client.id,
        email_account_id=account.id,
        direction=ClientEmailDirection.outbound,
        from_address=account.email_address,
        to_address=client.email,
        subject=subject,
        body_html=signed_html,
        body_text=signed_text,
        status=ClientEmailStatus.sending,
        in_reply_to=reference_ids[-1] if reference_ids else None,
        references=headers["References"] if headers else None,
    )
    db.add(message)
    await db.flush()

    message_id = await sender.send(
        from_address=f"{account.display_name or 'Team'} <{account.email_address}>",
        to_address=client.email,
        subject=subject,
        html_body=final_html,
        text_body=signed_text,
        headers=headers,
    )

    message.message_id = message_id
    message.status = ClientEmailStatus.sent
    message.sent_at = datetime.now(timezone.utc)
    await db.execute(
        update(EmailAccount)
        .where(EmailAccount.id == account.id)
        .values(sent_today=EmailAccount.sent_today + 1)
    )
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

    client_result = await db.execute(
        select(Client).where(
            Client.team_id == account.team_id,
            Client.email == from_email,
        )
    )
    client = client_result.scalar_one_or_none()
    if not client:
        raise NotFoundException("Inbound sender is not a known client")

    existing_message = None
    if raw_message_id:
        existing_result = await db.execute(
            select(ClientEmailMessage).where(
                ClientEmailMessage.team_id == account.team_id,
                ClientEmailMessage.message_id == raw_message_id,
            )
        )
        existing_message = existing_result.scalar_one_or_none()
    if existing_message:
        return {"conversation_id": None, "created": False}

    related_message = None
    reference_candidates = [value for value in [in_reply_to, references] if value]
    if reference_candidates:
        related_result = await db.execute(
            select(ClientEmailMessage)
            .where(
                ClientEmailMessage.team_id == account.team_id,
                or_(
                    ClientEmailMessage.message_id == in_reply_to,
                    ClientEmailMessage.message_id.in_(
                        [candidate.strip() for candidate in str(references or "").split() if candidate.strip()]
                    ),
                ),
            )
            .order_by(ClientEmailMessage.created_at.desc())
        )
        related_message = related_result.scalars().first()

    message = ClientEmailMessage(
        team_id=account.team_id,
        campaign_id=related_message.campaign_id if related_message else None,
        campaign_step_id=related_message.campaign_step_id if related_message else None,
        client_id=client.id,
        email_account_id=account.id,
        direction=ClientEmailDirection.inbound,
        from_address=from_email,
        to_address=to_email,
        subject=subject,
        body_html=body_html or None,
        body_text=body_text or None,
        message_id=raw_message_id,
        in_reply_to=in_reply_to,
        references=references,
        status=ClientEmailStatus.delivered,
        metadata_=payload,
    )
    db.add(message)
    await db.flush()

    # A reply halts any active follow-up sequence for this client. The B2B V1
    # rule is simply "any reply stops follow-ups" (no AI intent classification,
    # unlike the influencer pipeline) — without this, process_client_followups
    # would keep mailing scheduled steps to someone who already responded.
    enrollments_result = await db.execute(
        select(ClientCampaignEnrollment).where(
            ClientCampaignEnrollment.client_id == client.id,
            ClientCampaignEnrollment.status == ClientCampaignInfluencerStatus.in_progress,
        )
    )
    for enrollment in enrollments_result.scalars().all():
        enrollment.status = ClientCampaignInfluencerStatus.replied
    if client.status in (ClientStatus.new, ClientStatus.contacted):
        client.status = ClientStatus.replied

    conversation_result = await db.execute(
        select(ClientConversation).where(
            ClientConversation.team_id == account.team_id,
            ClientConversation.client_id == client.id,
        )
    )
    conversation = conversation_result.scalar_one_or_none()
    if not conversation:
        conversation = ClientConversation(
            team_id=account.team_id,
            client_id=client.id,
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
