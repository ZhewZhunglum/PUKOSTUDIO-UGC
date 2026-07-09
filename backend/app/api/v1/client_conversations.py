import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.client_conversation import (
    ClientConversationDetailResponse,
    ClientConversationListItemResponse,
    ClientConversationUpdateRequest,
    SendClientReplyRequest,
)
from app.services import client_conversation_service

router = APIRouter()


@router.get("", response_model=list[ClientConversationListItemResponse])
async def list_client_conversations(
    bucket: str = Query("all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_conversation_service.list_conversations(db, current_user.team_id, bucket)


@router.get("/{conversation_id}", response_model=ClientConversationDetailResponse)
async def get_client_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_conversation_service.get_conversation_detail(
        db, conversation_id, current_user.team_id
    )


@router.patch("/{conversation_id}", response_model=ClientConversationDetailResponse)
async def update_client_conversation(
    conversation_id: uuid.UUID,
    data: ClientConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_conversation_service.update_conversation(
        db,
        conversation_id,
        current_user.team_id,
        data.model_dump(exclude_unset=True),
    )


@router.post("/{conversation_id}/send-reply", response_model=ClientConversationDetailResponse)
async def send_client_reply(
    conversation_id: uuid.UUID,
    data: SendClientReplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_conversation_service.send_reply(
        db, conversation_id, current_user.team_id, data
    )
