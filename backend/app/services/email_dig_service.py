"""Batch email extraction jobs: queue, run, and write results back to the
influencer pool.

Input rows are fixed at create time (stored in job.results) so the Celery
worker only needs the job id. Write-back never overwrites an email a human
already filled in.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import async_session
from app.core.exceptions import BadRequestException, NotFoundException
from app.integrations.email_finder.digger import MAX_BATCH, dig_targets
from app.integrations.email_finder.resolve import resolve_target
from app.models.email_dig import EmailDigJob, EmailDigJobStatus
from app.models.influencer import Influencer, InfluencerPlatform, Platform
from app.schemas.email_dig import EmailDigJobCreate

# Commit progress every N processed rows so polling clients see movement
# without a commit per row.
PROGRESS_COMMIT_EVERY = 5


async def create_job(
    db: AsyncSession, team_id: uuid.UUID, data: EmailDigJobCreate
) -> EmailDigJob:
    rows: list[dict] = []

    for entry in data.entries:
        value = str(entry).strip()
        if value:
            rows.append({"entry": value, "status": "pending"})

    if data.influencer_ids:
        result = await db.execute(
            select(Influencer)
            .where(Influencer.id.in_(data.influencer_ids), Influencer.team_id == team_id)
        )
        influencers = {inf.id: inf for inf in result.scalars().all()}
        platform_rows = await db.execute(
            select(InfluencerPlatform).where(
                InfluencerPlatform.team_id == team_id,
                InfluencerPlatform.influencer_id.in_(list(influencers.keys()) or [uuid.uuid4()]),
            )
        )
        platforms_by_influencer: dict[uuid.UUID, InfluencerPlatform] = {}
        for platform in platform_rows.scalars().all():
            platforms_by_influencer.setdefault(platform.influencer_id, platform)

        for influencer_id in data.influencer_ids:
            influencer = influencers.get(influencer_id)
            if not influencer:
                continue
            platform = platforms_by_influencer.get(influencer_id)
            if not platform:
                rows.append(
                    {
                        "influencer_id": str(influencer_id),
                        "entry": influencer.name,
                        "status": "no-platform",
                    }
                )
                continue
            rows.append(
                {
                    "influencer_id": str(influencer_id),
                    "entry": platform.profile_url or platform.username,
                    "platform": platform.platform.value,
                    "handle": platform.username,
                    "status": "pending",
                }
            )

    if not rows:
        raise BadRequestException("没有可提取的输入：请提供用户名/链接或选择达人")
    if len(rows) > MAX_BATCH:
        raise BadRequestException(f"单次最多 {MAX_BATCH} 条，请分批提交")

    job = EmailDigJob(
        team_id=team_id,
        status=EmailDigJobStatus.queued,
        default_platform=data.default_platform,
        input_count=len(rows),
        results=rows,
    )
    db.add(job)
    await db.flush()
    return job


async def get_job(db: AsyncSession, team_id: uuid.UUID, job_id: uuid.UUID) -> EmailDigJob:
    result = await db.execute(
        select(EmailDigJob).where(EmailDigJob.id == job_id, EmailDigJob.team_id == team_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundException("Email dig job not found")
    return job


async def list_jobs(db: AsyncSession, team_id: uuid.UUID, limit: int = 20) -> list[EmailDigJob]:
    result = await db.execute(
        select(EmailDigJob)
        .where(EmailDigJob.team_id == team_id)
        .order_by(EmailDigJob.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _apply_row(db: AsyncSession, team_id: uuid.UUID, row: dict) -> str:
    """Write one dug row back to the influencer pool. Returns what happened:
    'updated' | 'created' | 'has-email' | 'no-email' | 'no-match-no-email' |
    'duplicate-email'."""
    emails = row.get("emails") or []
    email = emails[0] if emails else None
    phones = row.get("phones") or []
    phone = phones[0] if phones else None

    influencer: Influencer | None = None
    if row.get("influencer_id"):
        influencer = await db.get(Influencer, uuid.UUID(row["influencer_id"]))
        if influencer is not None and influencer.team_id != team_id:
            influencer = None
    else:
        platform_name = row.get("platform")
        handle = row.get("handle")
        if platform_name in ("tiktok", "instagram", "youtube") and handle:
            result = await db.execute(
                select(InfluencerPlatform).where(
                    InfluencerPlatform.team_id == team_id,
                    InfluencerPlatform.platform == Platform(platform_name),
                    func.lower(InfluencerPlatform.username) == handle.lower(),
                )
            )
            platform_row = result.scalars().first()
            if platform_row:
                influencer = await db.get(Influencer, platform_row.influencer_id)

    if influencer is not None:
        # Mark the outcome even when nothing was found, so the UI can show
        # "already dug" and nobody re-digs the same creator for nothing.
        influencer.email_dig_status = (
            "found" if (email or phone) else ("unreachable" if row.get("status") == "unreachable" else "no-email")
        )
        influencer.email_dig_at = datetime.now(timezone.utc)
        updated = False
        if phone and not influencer.phone:
            influencer.phone = phone
            influencer.phone_source = "dig"
            updated = True
        if email and not influencer.email:  # never overwrite a curated email
            influencer.email = email
            influencer.email_source = "dig"
            updated = True
        if updated:
            return "updated"
        return "has-email" if email and influencer.email else "no-email"

    if not email:
        return "no-match-no-email"

    # New creator dug from a raw entry — create it so the email flows straight
    # into campaigns without an export/import round trip.
    existing = await db.execute(
        select(Influencer).where(Influencer.team_id == team_id, Influencer.email == email)
    )
    if existing.scalars().first():
        return "duplicate-email"

    platform_name = row.get("platform")
    handle = row.get("handle") or row.get("entry") or email
    influencer = Influencer(
        team_id=team_id,
        name=row.get("display_name") or handle,
        email=email,
        phone=phone,
        email_source="dig" if email else None,
        phone_source="dig" if phone else None,
        email_dig_status="found",
        email_dig_at=datetime.now(timezone.utc),
        source="email_dig",
    )
    db.add(influencer)
    await db.flush()
    if platform_name in ("tiktok", "instagram", "youtube"):
        db.add(
            InfluencerPlatform(
                team_id=team_id,
                influencer_id=influencer.id,
                platform=Platform(platform_name),
                username=handle,
                profile_url=row.get("profile_url") or None,
                followers=row.get("follower_count"),
                raw_data={
                    "bio": row.get("bio"),
                    "links": row.get("links") or [],
                    "emails": emails,
                },
                last_synced_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()
    return "created"


async def run_job(job_id: uuid.UUID) -> None:
    async with async_session() as db:
        job = await db.get(EmailDigJob, job_id)
        if not job or job.status not in (EmailDigJobStatus.queued, EmailDigJobStatus.running):
            return

        job.status = EmailDigJobStatus.running
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        await db.commit()

        rows: list[dict] = [dict(row) for row in (job.results or [])]
        try:
            targets = []
            for row in rows:
                if row.get("status") == "no-platform":
                    targets.append(None)
                    continue
                targets.append(
                    resolve_target(row["entry"], row.get("platform") or job.default_platform)
                )

            # Concurrent dig workers all report through this session; AsyncSession
            # forbids concurrent use, so serialize progress writes.
            progress_lock = asyncio.Lock()

            async def on_result(index: int, result) -> None:
                if rows[index].get("status") == "no-platform":
                    return
                rows[index].update(result.as_dict())
                async with progress_lock:
                    job.processed_count += 1
                    if job.processed_count % PROGRESS_COMMIT_EVERY == 0:
                        job.results = rows
                        flag_modified(job, "results")
                        await db.commit()

            await dig_targets(
                targets,
                [row.get("entry", "") for row in rows],
                job.default_platform,
                on_result=on_result,
            )

            updated = 0
            created = 0
            for row in rows:
                if row.get("status") == "no-platform":
                    row["applied"] = "no-platform"
                    continue
                applied = await _apply_row(db, job.team_id, row)
                row["applied"] = applied
                if applied == "updated":
                    updated += 1
                elif applied == "created":
                    created += 1

            job.results = rows
            flag_modified(job, "results")
            job.processed_count = len(rows)
            job.resolved_count = sum(1 for t in targets if t is not None)
            job.found_count = sum(1 for row in rows if row.get("emails"))
            job.phone_found_count = sum(1 for row in rows if row.get("phones"))
            job.updated_count = updated
            job.created_count = created
            job.status = EmailDigJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — job must record any failure
            await db.rollback()
            job.status = EmailDigJobStatus.failed
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
