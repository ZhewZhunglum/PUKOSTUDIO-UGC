import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.ai import CampaignAIPlaybookResponse, CampaignAIPlaybookUpsert
from app.schemas.campaign import (
    CampaignCreate,
    CampaignEnrollmentResponse,
    CampaignResponse,
    CampaignUpdate,
    EnrollInfluencersRequest,
)
from app.services import ai_communication_service, campaign_service, sop_service

router = APIRouter()


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.list_campaigns(db, current_user.team_id)


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.create_campaign(db, current_user.team_id, data)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.get_campaign(db, campaign_id, current_user.team_id)


@router.get("/{campaign_id}/ai-playbook", response_model=CampaignAIPlaybookResponse)
async def get_campaign_ai_playbook(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.get_campaign_playbook(
        db, campaign_id, current_user.team_id
    )


@router.put("/{campaign_id}/ai-playbook", response_model=CampaignAIPlaybookResponse)
async def upsert_campaign_ai_playbook(
    campaign_id: uuid.UUID,
    data: CampaignAIPlaybookUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ai_communication_service.upsert_campaign_playbook(
        db,
        campaign_id,
        current_user.team_id,
        data.model_dump(),
    )


@router.post(
    "/{campaign_id}/ai-playbook/apply-sop",
    response_model=CampaignAIPlaybookResponse,
)
async def apply_sop_to_campaign_ai_playbook(
    campaign_id: uuid.UUID,
    overwrite: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sop_service.apply_sop_defaults_to_playbook(
        db,
        campaign_id,
        current_user.team_id,
        overwrite=overwrite,
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.update_campaign(
        db, campaign_id, current_user.team_id, data
    )


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.start_campaign(db, campaign_id, current_user.team_id)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.pause_campaign(db, campaign_id, current_user.team_id)


@router.post("/{campaign_id}/stop", response_model=CampaignResponse)
async def stop_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.stop_campaign(db, campaign_id, current_user.team_id)


@router.post("/{campaign_id}/enroll")
async def enroll_influencers(
    campaign_id: uuid.UUID,
    data: EnrollInfluencersRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await campaign_service.enroll_influencers(
        db, campaign_id, current_user.team_id, data.influencer_ids
    )
    return {"enrolled": count}


@router.get("/{campaign_id}/enrollments", response_model=list[CampaignEnrollmentResponse])
async def list_campaign_enrollments(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.list_campaign_enrollments(
        db, campaign_id, current_user.team_id
    )


@router.delete("/{campaign_id}/enrollments/{enrollment_id}", status_code=204)
async def remove_campaign_enrollment(
    campaign_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await campaign_service.remove_enrollment(
        db, campaign_id, current_user.team_id, enrollment_id
    )


@router.get("/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify access
    await campaign_service.get_campaign(db, campaign_id, current_user.team_id)
    return await campaign_service.get_campaign_stats(db, campaign_id)
