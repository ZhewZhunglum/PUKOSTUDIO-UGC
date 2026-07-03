import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.utils import ai_is_configured, build_ai_thread, strip_html
from app.integrations.ai.factory import get_team_ai_provider
from app.models.ai import (
    AIActionLog,
    AIActionType,
    AIDraftStatus,
    AIMessageDraft,
    AIRiskLevel,
    CampaignAIPlaybook,
)
from app.models.campaign import Campaign, CampaignInfluencer, CampaignInfluencerStatus
from app.models.conversation import AIIntent, Conversation
from app.models.email_message import EmailDirection, EmailMessage
from app.models.influencer import Influencer, InfluencerStatus

PLAYBOOK_FIELDS = [
    "enabled",
    "product_name",
    "product_description",
    "offer_summary",
    "deliverables",
    "sample_policy",
    "pricing_rules",
    "negotiation_limits",
    "prohibited_claims",
    "tone",
    "language",
    "signature",
    "reply_guidelines",
    "campaign_objectives",
    "target_audience",
    "key_messages",
    "content_dos",
    "content_donts",
    "required_hashtags",
    "disclosure_requirements",
    "payment_terms",
    "usage_rights",
    "approval_process",
    "contract_required",
    "content_review_checklist",
    "posting_guidance",
    "performance_kpis",
    "competitor_notes",
]


def empty_playbook_response(campaign_id: uuid.UUID) -> dict:
    return {
        "id": None,
        "campaign_id": campaign_id,
        "enabled": False,
        "product_name": None,
        "product_description": None,
        "offer_summary": None,
        "deliverables": None,
        "sample_policy": None,
        "pricing_rules": None,
        "negotiation_limits": None,
        "prohibited_claims": None,
        "tone": None,
        "language": None,
        "signature": None,
        "reply_guidelines": None,
        "campaign_objectives": None,
        "target_audience": None,
        "key_messages": None,
        "content_dos": None,
        "content_donts": None,
        "required_hashtags": None,
        "disclosure_requirements": None,
        "payment_terms": None,
        "usage_rights": None,
        "approval_process": None,
        "contract_required": False,
        "content_review_checklist": None,
        "posting_guidance": None,
        "performance_kpis": None,
        "competitor_notes": None,
        "created_at": None,
        "updated_at": None,
    }


def _reply_subject(subject: str | None) -> str:
    base_subject = (subject or "Hello").strip()
    if base_subject.lower().startswith("re:"):
        return base_subject
    return f"Re: {base_subject}"


def _safe_intent(value: str | None) -> AIIntent:
    try:
        return AIIntent(value or AIIntent.unknown.value)
    except ValueError:
        return AIIntent.unknown


def _normalize_risk(intent: AIIntent, confidence: float | None, raw: str | None = None) -> AIRiskLevel:
    if raw in {level.value for level in AIRiskLevel}:
        return AIRiskLevel(raw)
    if intent in {AIIntent.negotiation, AIIntent.unknown, AIIntent.spam}:
        return AIRiskLevel.high
    if intent == AIIntent.question or (confidence is not None and confidence < 0.75):
        return AIRiskLevel.medium
    return AIRiskLevel.low


def _playbook_context(playbook: CampaignAIPlaybook) -> dict:
    return {field: getattr(playbook, field) for field in PLAYBOOK_FIELDS}


def _as_optional_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


async def _log_action(
    db: AsyncSession,
    *,
    team_id: uuid.UUID,
    action_type: AIActionType,
    conversation_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    draft_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        AIActionLog(
            team_id=team_id,
            conversation_id=conversation_id,
            campaign_id=campaign_id,
            draft_id=draft_id,
            action_type=action_type,
            actor_user_id=actor_user_id,
            detail=detail or {},
        )
    )


async def _get_campaign(db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID) -> Campaign:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.team_id == team_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise NotFoundException("Campaign not found")
    return campaign


async def _get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID, team_id: uuid.UUID | None = None
) -> tuple[Conversation, Influencer]:
    query = (
        select(Conversation, Influencer)
        .join(Influencer, Influencer.id == Conversation.influencer_id)
        .where(Conversation.id == conversation_id)
    )
    if team_id:
        query = query.where(Conversation.team_id == team_id)
    row = (await db.execute(query)).one_or_none()
    if not row:
        raise NotFoundException("Conversation not found")
    return row


async def _conversation_messages(
    db: AsyncSession, conversation: Conversation
) -> list[EmailMessage]:
    result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == conversation.team_id,
            EmailMessage.influencer_id == conversation.influencer_id,
        )
        .order_by(EmailMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def _latest_campaign_id(
    db: AsyncSession, conversation: Conversation
) -> uuid.UUID | None:
    result = await db.execute(
        select(EmailMessage.campaign_id)
        .where(
            EmailMessage.team_id == conversation.team_id,
            EmailMessage.influencer_id == conversation.influencer_id,
            EmailMessage.campaign_id.is_not(None),
        )
        .order_by(EmailMessage.created_at.desc())
    )
    return result.scalars().first()


async def _latest_inbound_message(
    db: AsyncSession, conversation: Conversation
) -> EmailMessage | None:
    result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == conversation.team_id,
            EmailMessage.influencer_id == conversation.influencer_id,
            EmailMessage.direction == EmailDirection.inbound,
        )
        .order_by(EmailMessage.created_at.desc())
    )
    return result.scalars().first()


async def _pending_draft_for_latest_inbound(
    db: AsyncSession, conversation: Conversation
) -> AIMessageDraft | None:
    latest_inbound = await _latest_inbound_message(db, conversation)
    if not latest_inbound:
        return None
    result = await db.execute(
        select(AIMessageDraft)
        .where(
            AIMessageDraft.conversation_id == conversation.id,
            AIMessageDraft.status == AIDraftStatus.pending_review,
            AIMessageDraft.created_at >= latest_inbound.created_at,
        )
        .order_by(AIMessageDraft.created_at.desc())
    )
    return result.scalars().first()


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

    result = await db.execute(
        select(CampaignInfluencer).where(
            CampaignInfluencer.influencer_id == conversation.influencer_id
        )
    )
    for enrollment in result.scalars().all():
        enrollment.status = campaign_status


async def get_campaign_playbook(
    db: AsyncSession, campaign_id: uuid.UUID, team_id: uuid.UUID
) -> CampaignAIPlaybook | dict:
    await _get_campaign(db, campaign_id, team_id)
    result = await db.execute(
        select(CampaignAIPlaybook).where(CampaignAIPlaybook.campaign_id == campaign_id)
    )
    playbook = result.scalar_one_or_none()
    return playbook or empty_playbook_response(campaign_id)


async def upsert_campaign_playbook(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: dict,
) -> CampaignAIPlaybook:
    await _get_campaign(db, campaign_id, team_id)
    result = await db.execute(
        select(CampaignAIPlaybook).where(CampaignAIPlaybook.campaign_id == campaign_id)
    )
    playbook = result.scalar_one_or_none()
    if not playbook:
        playbook = CampaignAIPlaybook(campaign_id=campaign_id)
        db.add(playbook)
    for field in PLAYBOOK_FIELDS:
        if field in payload:
            setattr(playbook, field, payload[field])
    await db.flush()
    return playbook


async def classify_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    team_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> Conversation:
    conversation, influencer = await _get_conversation(db, conversation_id, team_id)
    if not ai_is_configured():
        conversation.needs_review = True
        await _log_action(
            db,
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            action_type=AIActionType.classification_skipped,
            actor_user_id=actor_user_id,
            detail={"reason": "AI provider is not configured"},
        )
        await db.flush()
        return conversation

    messages = await _conversation_messages(db, conversation)
    provider = await get_team_ai_provider(db, conversation.team_id)
    result = await provider.classify_reply(build_ai_thread(messages))
    intent = _safe_intent(result.get("intent"))
    confidence = float(result.get("confidence", 0))
    risk_level = _normalize_risk(intent, confidence, result.get("risk_level"))

    conversation.ai_intent = intent
    conversation.ai_confidence = confidence
    conversation.needs_review = confidence < 0.85 or risk_level != AIRiskLevel.low
    await _apply_intent_mapping(db, conversation, influencer, intent)
    await _log_action(
        db,
        team_id=conversation.team_id,
        conversation_id=conversation.id,
        campaign_id=await _latest_campaign_id(db, conversation),
        action_type=AIActionType.classified,
        actor_user_id=actor_user_id,
        detail={
            "intent": intent.value,
            "confidence": confidence,
            "risk_level": risk_level.value,
            "summary": result.get("summary"),
        },
    )
    await db.flush()
    return conversation


async def create_ai_draft(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    team_id: uuid.UUID,
    guidelines: str = "",
    auto: bool = False,
) -> AIMessageDraft:
    conversation, _ = await _get_conversation(db, conversation_id, team_id)
    if auto:
        existing = await _pending_draft_for_latest_inbound(db, conversation)
        if existing:
            return existing

    if not conversation.ai_intent and ai_is_configured():
        await classify_conversation(db, conversation_id, team_id)

    messages = await _conversation_messages(db, conversation)
    latest_message = messages[-1] if messages else None
    campaign_id = await _latest_campaign_id(db, conversation)
    subject = _reply_subject(latest_message.subject if latest_message else None)
    intent = conversation.ai_intent.value if conversation.ai_intent else AIIntent.unknown.value
    confidence = conversation.ai_confidence

    def failed_draft(reason: str) -> AIMessageDraft:
        return AIMessageDraft(
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            campaign_id=campaign_id,
            influencer_id=conversation.influencer_id,
            subject=subject,
            body_html="",
            body_text="",
            intent=intent,
            confidence=confidence,
            risk_level=AIRiskLevel.high,
            status=AIDraftStatus.failed,
            failure_reason=reason,
            metadata_={"auto": auto},
        )

    if not ai_is_configured():
        draft = failed_draft("AI provider is not configured")
        db.add(draft)
        await db.flush()
        await _log_action(
            db,
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            campaign_id=campaign_id,
            draft_id=draft.id,
            action_type=AIActionType.draft_failed,
            detail={"reason": draft.failure_reason},
        )
        return draft

    if not campaign_id:
        draft = failed_draft("Conversation is not linked to a campaign")
        db.add(draft)
        await db.flush()
        await _log_action(
            db,
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            draft_id=draft.id,
            action_type=AIActionType.draft_failed,
            detail={"reason": draft.failure_reason},
        )
        return draft

    playbook_result = await db.execute(
        select(CampaignAIPlaybook).where(
            CampaignAIPlaybook.campaign_id == campaign_id,
            CampaignAIPlaybook.enabled.is_(True),
        )
    )
    playbook = playbook_result.scalar_one_or_none()
    if not playbook:
        draft = failed_draft("Campaign AI playbook is not configured or not enabled")
        db.add(draft)
        await db.flush()
        await _log_action(
            db,
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            campaign_id=campaign_id,
            draft_id=draft.id,
            action_type=AIActionType.draft_failed,
            detail={"reason": draft.failure_reason},
        )
        return draft

    combined_guidelines = "\n\n".join(
        part for part in [playbook.reply_guidelines, guidelines] if part
    )
    provider = await get_team_ai_provider(db, conversation.team_id)
    try:
        result = await provider.draft_reply(
            build_ai_thread(messages),
            intent,
            combined_guidelines,
            playbook=_playbook_context(playbook),
        )
        body_html = result.get("body_html") or ""
        body_text = result.get("body_text") or strip_html(body_html)
        draft = AIMessageDraft(
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            campaign_id=campaign_id,
            influencer_id=conversation.influencer_id,
            subject=result.get("subject") or subject,
            body_html=body_html,
            body_text=body_text,
            intent=intent,
            confidence=confidence,
            risk_level=_normalize_risk(_safe_intent(intent), confidence, result.get("risk_level")),
            status=AIDraftStatus.pending_review,
            rationale=_as_optional_text(result.get("rationale")),
            missing_context=_as_optional_text(result.get("missing_context")),
            metadata_={"auto": auto, "playbook_id": str(playbook.id)},
        )
        db.add(draft)
        conversation.needs_review = True
        await db.flush()
        await _log_action(
            db,
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            campaign_id=campaign_id,
            draft_id=draft.id,
            action_type=AIActionType.draft_generated,
            detail={"risk_level": draft.risk_level.value, "intent": intent},
        )
        return draft
    except Exception as exc:
        draft = failed_draft(str(exc))
        db.add(draft)
        await db.flush()
        await _log_action(
            db,
            team_id=conversation.team_id,
            conversation_id=conversation.id,
            campaign_id=campaign_id,
            draft_id=draft.id,
            action_type=AIActionType.draft_failed,
            detail={"reason": str(exc)},
        )
        return draft


async def process_inbound_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> AIMessageDraft | None:
    conversation, _ = await _get_conversation(db, conversation_id)
    await classify_conversation(db, conversation_id, conversation.team_id)
    if conversation.ai_intent == AIIntent.spam:
        return None
    return await create_ai_draft(db, conversation_id, conversation.team_id, auto=True)


async def list_ai_drafts(
    db: AsyncSession, conversation_id: uuid.UUID, team_id: uuid.UUID
) -> list[AIMessageDraft]:
    await _get_conversation(db, conversation_id, team_id)
    result = await db.execute(
        select(AIMessageDraft)
        .where(AIMessageDraft.conversation_id == conversation_id, AIMessageDraft.team_id == team_id)
        .order_by(AIMessageDraft.created_at.desc())
    )
    return list(result.scalars().all())


async def update_ai_draft(
    db: AsyncSession,
    draft_id: uuid.UUID,
    team_id: uuid.UUID,
    payload: dict,
    actor_user_id: uuid.UUID,
) -> AIMessageDraft:
    draft = await _get_draft(db, draft_id, team_id)
    if draft.status not in {AIDraftStatus.pending_review, AIDraftStatus.failed}:
        raise BadRequestException("Only pending or failed drafts can be edited")
    for field in ["subject", "body_html", "body_text"]:
        if field in payload and payload[field] is not None:
            setattr(draft, field, payload[field])
    if "body_html" in payload and payload["body_html"] is not None and "body_text" not in payload:
        draft.body_text = strip_html(payload["body_html"])
    if draft.status == AIDraftStatus.failed and draft.body_html.strip():
        draft.status = AIDraftStatus.pending_review
        draft.failure_reason = None
    await db.flush()
    await _log_action(
        db,
        team_id=team_id,
        conversation_id=draft.conversation_id,
        campaign_id=draft.campaign_id,
        draft_id=draft.id,
        action_type=AIActionType.draft_updated,
        actor_user_id=actor_user_id,
        detail={"fields": list(payload.keys())},
    )
    return draft


async def _get_draft(db: AsyncSession, draft_id: uuid.UUID, team_id: uuid.UUID) -> AIMessageDraft:
    result = await db.execute(
        select(AIMessageDraft).where(AIMessageDraft.id == draft_id, AIMessageDraft.team_id == team_id)
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise NotFoundException("AI draft not found")
    return draft


async def approve_and_send_draft(
    db: AsyncSession,
    draft_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    attachment_ids: list[uuid.UUID] | None = None,
) -> AIMessageDraft:
    draft = await _get_draft(db, draft_id, team_id)
    if draft.status != AIDraftStatus.pending_review:
        raise BadRequestException("Only pending drafts can be approved and sent")
    if not draft.body_html.strip():
        raise BadRequestException("Draft body is empty")

    draft.status = AIDraftStatus.approved
    draft.approved_by = actor_user_id
    draft.approved_at = datetime.now(timezone.utc)
    await _log_action(
        db,
        team_id=team_id,
        conversation_id=draft.conversation_id,
        campaign_id=draft.campaign_id,
        draft_id=draft.id,
        action_type=AIActionType.draft_approved,
        actor_user_id=actor_user_id,
    )

    from app.schemas.conversation import SendReplyRequest
    from app.services import conversation_service

    try:
        await conversation_service.send_reply(
            db,
            draft.conversation_id,
            team_id,
            SendReplyRequest(
                subject=draft.subject,
                body_html=draft.body_html,
                body_text=draft.body_text,
                attachment_ids=attachment_ids or [],
            ),
        )
    except Exception as exc:
        draft.status = AIDraftStatus.failed
        draft.failure_reason = str(exc)
        await db.flush()
        await _log_action(
            db,
            team_id=team_id,
            conversation_id=draft.conversation_id,
            campaign_id=draft.campaign_id,
            draft_id=draft.id,
            action_type=AIActionType.draft_failed,
            actor_user_id=actor_user_id,
            detail={"reason": str(exc)},
        )
        return draft

    latest_message_result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == team_id,
            EmailMessage.influencer_id == draft.influencer_id,
            EmailMessage.direction == EmailDirection.outbound,
        )
        .order_by(EmailMessage.created_at.desc())
    )
    latest_message = latest_message_result.scalars().first()
    draft.status = AIDraftStatus.sent
    draft.sent_message_id = latest_message.id if latest_message else None
    await db.flush()
    await _log_action(
        db,
        team_id=team_id,
        conversation_id=draft.conversation_id,
        campaign_id=draft.campaign_id,
        draft_id=draft.id,
        action_type=AIActionType.draft_sent,
        actor_user_id=actor_user_id,
        detail={"sent_message_id": str(draft.sent_message_id) if draft.sent_message_id else None},
    )
    return draft


async def discard_ai_draft(
    db: AsyncSession,
    draft_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> AIMessageDraft:
    draft = await _get_draft(db, draft_id, team_id)
    if draft.status == AIDraftStatus.sent:
        raise BadRequestException("Sent drafts cannot be discarded")
    draft.status = AIDraftStatus.discarded
    await db.flush()
    await _log_action(
        db,
        team_id=team_id,
        conversation_id=draft.conversation_id,
        campaign_id=draft.campaign_id,
        draft_id=draft.id,
        action_type=AIActionType.draft_discarded,
        actor_user_id=actor_user_id,
    )
    return draft


async def list_action_logs(
    db: AsyncSession,
    team_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> list[AIActionLog]:
    query = select(AIActionLog).where(AIActionLog.team_id == team_id)
    if conversation_id:
        query = query.where(AIActionLog.conversation_id == conversation_id)
    result = await db.execute(query.order_by(AIActionLog.created_at.desc()))
    return list(result.scalars().all())
