"""
Discovery API — trigger social media scrapers and retrieve results.
"""
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException
from app.dependencies import get_current_user
from app.integrations.scrapers.manager import get_suggested_hashtags, run_scrape_job
from app.integrations.woto import WotoAPIError, WotoConfigurationError
from app.models.user import User
from app.schemas.woto import (
    WotoCostEstimateResponse,
    WotoDictionaryItem,
    WotoPricingTableResponse,
    WotoQuotaResponse,
    WotoSyncJobCreate,
    WotoSyncJobResponse,
)
from app.services import woto_pricing_service, woto_service

router = APIRouter()

# In-memory job tracker (suitable for single-worker dev; replace with Redis for prod)
_jobs: dict[str, dict] = {}


class ScrapeRequest(BaseModel):
    platform: Literal["tiktok", "instagram"] = "tiktok"
    hashtag: str = Field(..., min_length=1, max_length=100, examples=["supplements"])
    limit: int = Field(default=30, ge=5, le=100)
    niche: str | None = Field(default=None, examples=["protein"])
    country: str = Field(default="US", max_length=2)


class ScrapeJobResponse(BaseModel):
    job_id: str
    status: str
    platform: str
    hashtag: str
    message: str


class ScrapeStatusResponse(BaseModel):
    job_id: str
    status: str
    platform: str | None = None
    hashtag: str | None = None
    discovered: int = 0
    inserted: int = 0
    skipped: int = 0
    error: str | None = None


async def _run_and_track(
    job_id: str,
    db: AsyncSession,
    team_id: uuid.UUID,
    req: ScrapeRequest,
) -> None:
    _jobs[job_id]["status"] = "running"
    try:
        result = await run_scrape_job(
            db=db,
            team_id=team_id,
            platform=req.platform,
            hashtag=req.hashtag,
            limit=req.limit,
            niche=req.niche,
            country=req.country,
        )
        await db.commit()
        _jobs[job_id].update(
            status="completed",
            discovered=result.get("discovered", 0),
            inserted=result.get("inserted", 0),
            skipped=result.get("skipped", 0),
        )
    except Exception as exc:
        await db.rollback()
        _jobs[job_id].update(status="failed", error=str(exc))


@router.post("/scrape", response_model=ScrapeJobResponse, status_code=202)
async def start_scrape(
    req: ScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an async scrape job for a platform hashtag."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "platform": req.platform,
        "hashtag": req.hashtag,
        "discovered": 0,
        "inserted": 0,
        "skipped": 0,
        "error": None,
    }
    background_tasks.add_task(
        _run_and_track, job_id, db, current_user.team_id, req
    )
    return ScrapeJobResponse(
        job_id=job_id,
        status="queued",
        platform=req.platform,
        hashtag=req.hashtag,
        message=f"Scrape job queued for #{req.hashtag} on {req.platform}. Poll /status/{job_id} for progress.",
    )


@router.get("/status/{job_id}", response_model=ScrapeStatusResponse)
async def get_scrape_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Poll a scrape job's current status."""
    job = _jobs.get(job_id)
    if not job:
        return ScrapeStatusResponse(job_id=job_id, status="not_found")
    return ScrapeStatusResponse(job_id=job_id, **job)


@router.get("/hashtags")
async def get_hashtag_suggestions(
    platform: Literal["tiktok", "instagram"] = Query(default="tiktok"),
    current_user: User = Depends(get_current_user),
):
    """Return suggested supplement hashtags for a platform."""
    return {
        "platform": platform,
        "hashtags": get_suggested_hashtags(platform),
    }


@router.get("/woto/quota", response_model=WotoQuotaResponse)
async def get_woto_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await woto_service.query_quota(db=db, team_id=current_user.team_id)
    except WotoConfigurationError as exc:
        raise BadRequestException(str(exc)) from exc
    except WotoAPIError as exc:
        raise BadRequestException(str(exc)) from exc


@router.get("/woto/dictionaries", response_model=list[WotoDictionaryItem])
async def get_woto_dictionary(
    dict_type_code: Literal["blog_cate_new", "dim_region"] = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await woto_service.list_dictionary(dict_type_code, db=db, team_id=current_user.team_id)
    except WotoConfigurationError as exc:
        raise BadRequestException(str(exc)) from exc
    except WotoAPIError as exc:
        raise BadRequestException(str(exc)) from exc


@router.get("/woto/pricing", response_model=WotoPricingTableResponse)
async def get_woto_pricing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await woto_pricing_service.get_pricing_table(db, current_user.team_id)


@router.post("/woto/pricing/estimate", response_model=WotoCostEstimateResponse)
async def estimate_woto_sync_cost(
    data: WotoSyncJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await woto_pricing_service.estimate_sync_cost(db, current_user.team_id, data)


@router.post("/woto/sync-jobs", response_model=WotoSyncJobResponse, status_code=202)
async def create_woto_sync_job(
    data: WotoSyncJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await woto_service.create_sync_job(db, current_user.team_id, data)
    await db.commit()

    from app.workers.woto_tasks import sync_woto_influencers

    sync_woto_influencers.delay(str(job.id))
    return job


@router.get("/woto/sync-jobs", response_model=list[WotoSyncJobResponse])
async def list_woto_sync_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await woto_service.list_sync_jobs(db, current_user.team_id, limit=limit)


@router.get("/woto/sync-jobs/{job_id}", response_model=WotoSyncJobResponse)
async def get_woto_sync_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await woto_service.get_sync_job(db, current_user.team_id, job_id)
