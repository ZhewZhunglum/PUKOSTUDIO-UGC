import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.dependencies import get_current_user
from app.models.suppression import SuppressionReason
from app.models.user import User
from app.services import suppression_service

router = APIRouter()


class SuppressionCreate(BaseModel):
    email: EmailStr


class SuppressionResponse(BaseModel):
    id: uuid.UUID
    email: str
    reason: SuppressionReason
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SuppressionResponse])
async def list_suppressions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await suppression_service.list_suppressions(db, current_user.team_id)


@router.post("", response_model=list[SuppressionResponse], status_code=201)
async def add_suppression(
    data: SuppressionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await suppression_service.add_suppression(
        db, current_user.team_id, data.email, SuppressionReason.manual
    )
    await db.flush()
    return await suppression_service.list_suppressions(db, current_user.team_id)


@router.delete("/{suppression_id}", status_code=204)
async def remove_suppression(
    suppression_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    removed = await suppression_service.remove_suppression(
        db, current_user.team_id, suppression_id
    )
    if not removed:
        raise NotFoundException("Suppression entry not found")
