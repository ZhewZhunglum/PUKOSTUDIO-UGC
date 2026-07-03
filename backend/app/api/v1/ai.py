import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.ai import AIActionLogResponse, AIMessageDraftResponse, AIMessageDraftUpdate
from app.services import ai_communication_service

router = APIRouter()


class ApproveSendRequest(BaseModel):
    attachment_ids: list[uuid.UUID] = []


@router.patch("/ai-drafts/{draft_id}", response_model=AIMessageDraftResponse)
async def update_ai_draft(
    draft_id: uuid.UUID,
    data: AIMessageDraftUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.update_ai_draft(
        db,
        draft_id,
        current_user.team_id,
        data.model_dump(exclude_unset=True),
        current_user.id,
    )


@router.post("/ai-drafts/{draft_id}/approve-send", response_model=AIMessageDraftResponse)
async def approve_and_send_ai_draft(
    draft_id: uuid.UUID,
    data: ApproveSendRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.approve_and_send_draft(
        db,
        draft_id,
        current_user.team_id,
        current_user.id,
        attachment_ids=(data.attachment_ids if data else None),
    )


@router.post("/ai-drafts/{draft_id}/discard", response_model=AIMessageDraftResponse)
async def discard_ai_draft(
    draft_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.discard_ai_draft(
        db, draft_id, current_user.team_id, current_user.id
    )


@router.get("/ai-action-logs", response_model=list[AIActionLogResponse])
async def list_ai_action_logs(
    conversation_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.list_action_logs(
        db, current_user.team_id, conversation_id
    )
