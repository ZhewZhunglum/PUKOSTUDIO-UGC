import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.sop import SOPInfluencerScore, SOPPlaybookResponse
from app.services import sop_service

router = APIRouter()


@router.get("/sop/playbook", response_model=SOPPlaybookResponse)
async def get_sop_playbook(
    current_user: User = Depends(get_current_user),
):
    return sop_service.get_sop_playbook()


@router.get("/sop/influencer-score/{influencer_id}", response_model=SOPInfluencerScore)
async def get_sop_influencer_score(
    influencer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sop_service.get_influencer_score(db, influencer_id, current_user.team_id)
