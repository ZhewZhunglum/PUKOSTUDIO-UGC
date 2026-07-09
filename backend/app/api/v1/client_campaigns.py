import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tabular import normalize_format, tabular_response
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.client_campaign import (
    ClientCampaignCreate,
    ClientCampaignEnrollmentResponse,
    ClientCampaignResponse,
    ClientCampaignUpdate,
    EnrollClientsRequest,
)
from app.services import client_campaign_service

router = APIRouter()


@router.get("", response_model=list[ClientCampaignResponse])
async def list_client_campaigns(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.list_campaigns(db, current_user.team_id)


@router.post("", response_model=ClientCampaignResponse, status_code=201)
async def create_client_campaign(
    data: ClientCampaignCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.create_campaign(db, current_user.team_id, data)


@router.get("/{campaign_id}", response_model=ClientCampaignResponse)
async def get_client_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.get_campaign(db, campaign_id, current_user.team_id)


@router.put("/{campaign_id}", response_model=ClientCampaignResponse)
async def update_client_campaign(
    campaign_id: uuid.UUID,
    data: ClientCampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.update_campaign(
        db, campaign_id, current_user.team_id, data
    )


@router.post("/{campaign_id}/start", response_model=ClientCampaignResponse)
async def start_client_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.start_campaign(
        db, campaign_id, current_user.team_id
    )


@router.post("/{campaign_id}/pause", response_model=ClientCampaignResponse)
async def pause_client_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.pause_campaign(
        db, campaign_id, current_user.team_id
    )


@router.post("/{campaign_id}/stop", response_model=ClientCampaignResponse)
async def stop_client_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.stop_campaign(
        db, campaign_id, current_user.team_id
    )


@router.post("/{campaign_id}/enroll")
async def enroll_clients(
    campaign_id: uuid.UUID,
    data: EnrollClientsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await client_campaign_service.enroll_clients(
        db, campaign_id, current_user.team_id, data.client_ids
    )
    return {"enrolled": count}


@router.get(
    "/{campaign_id}/enrollments", response_model=list[ClientCampaignEnrollmentResponse]
)
async def list_client_campaign_enrollments(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.list_campaign_enrollments(
        db, campaign_id, current_user.team_id
    )


@router.get("/{campaign_id}/enrollments/export")
async def export_client_campaign_enrollments(
    campaign_id: uuid.UUID,
    format: str = Query("csv"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fmt = normalize_format(format)
    enrollments = await client_campaign_service.list_campaign_enrollments(
        db, campaign_id, current_user.team_id
    )
    headers = [
        "client_company_name", "client_email", "status", "current_step",
        "last_email_status", "last_sent_at", "enrolled_at", "failure_reason",
    ]
    rows = [
        [
            e["client_company_name"],
            e["client_email"] or "",
            e["status"],
            e["current_step"],
            e["last_email_status"] or "",
            e["last_sent_at"],
            e["enrolled_at"],
            e["failure_reason"] or "",
        ]
        for e in enrollments
    ]
    return tabular_response(
        fmt=fmt,
        filename_stem=f"client_campaign_{campaign_id}_enrollments",
        headers=headers,
        rows=rows,
        sheet_title="Enrollments",
    )


@router.delete("/{campaign_id}/enrollments/{enrollment_id}", status_code=204)
async def remove_client_campaign_enrollment(
    campaign_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await client_campaign_service.remove_enrollment(
        db, campaign_id, current_user.team_id, enrollment_id
    )


@router.get("/{campaign_id}/send-progress")
async def get_client_campaign_send_progress(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_campaign_service.get_send_progress(
        db, campaign_id, current_user.team_id
    )


@router.get("/{campaign_id}/stats")
async def get_client_campaign_stats(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await client_campaign_service.get_campaign(db, campaign_id, current_user.team_id)
    return await client_campaign_service.get_campaign_stats(db, campaign_id)
