import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.ai import AIMessageDraftResponse
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationListItemResponse,
    ConversationUpdateRequest,
    ReplyDraftRequest,
    SendReplyRequest,
)
from app.services import ai_communication_service, conversation_service

router = APIRouter()


@router.get("", response_model=list[ConversationListItemResponse])
async def list_conversations(
    bucket: str = Query("all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.list_conversations(db, current_user.team_id, bucket)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.get_conversation_detail(
        db, conversation_id, current_user.team_id
    )


@router.patch("/{conversation_id}", response_model=ConversationDetailResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    data: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.update_conversation(
        db,
        conversation_id,
        current_user.team_id,
        data.model_dump(exclude_unset=True),
    )


@router.post("/{conversation_id}/classify", response_model=ConversationDetailResponse)
async def classify_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ai_communication_service.classify_conversation(
        db, conversation_id, current_user.team_id, current_user.id
    )
    return await conversation_service.get_conversation_detail(
        db, conversation_id, current_user.team_id
    )


@router.get("/{conversation_id}/ai-drafts", response_model=list[AIMessageDraftResponse])
async def list_ai_drafts(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.list_ai_drafts(
        db, conversation_id, current_user.team_id
    )


@router.post("/{conversation_id}/ai-drafts", response_model=AIMessageDraftResponse)
async def create_ai_draft(
    conversation_id: uuid.UUID,
    data: ReplyDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.create_ai_draft(
        db, conversation_id, current_user.team_id, data.guidelines
    )


@router.post("/{conversation_id}/draft-reply", response_model=AIMessageDraftResponse)
async def draft_reply(
    conversation_id: uuid.UUID,
    data: ReplyDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.draft_reply(
        db, conversation_id, current_user.team_id, data.guidelines
    )


@router.post("/{conversation_id}/send-reply", response_model=ConversationDetailResponse)
async def send_reply(
    conversation_id: uuid.UUID,
    data: SendReplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.send_reply(
        db, conversation_id, current_user.team_id, data
    )
