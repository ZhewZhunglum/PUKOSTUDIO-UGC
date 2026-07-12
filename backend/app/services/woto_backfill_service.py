"""Woto contact backfill: fill missing emails/phones for EXISTING influencers
via the paid Woto database, as a fallback after the free public-profile dig.

Reuses the EmailDigJob table (mode="woto") so the UI polls the same endpoint.
Per row: resolve the creator's Woto channelUid (stored external_id, else a NAME
search — billed), then unlock contact info (billed only when an email comes
back, mirroring the manual woto-refresh flow). Never overwrites data a human
already filled in. Completely independent from the discovery page's Woto sync.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import async_session
from app.core.exceptions import BadRequestException
from app.integrations.woto import WotoAPIError
from app.models.email_dig import EmailDigJob, EmailDigJobStatus
from app.models.influencer import Influencer, InfluencerPlatform, Platform
from app.models.woto import WotoBillingOperation
from app.services import woto_pricing_service, woto_service

MAX_BATCH = 1000

_PHONE_KEYS = ("phone", "phonenumber", "mobile", "whatsapp", "whatsappnumber", "tel", "telephone")
_PHONE_RE = re.compile(r"\+?\d[\d\-().\s]{5,18}\d")


def _extract_phone(value: Any) -> str | None:
    """Best-effort phone/WhatsApp number from a Woto contact payload."""
    if not value:
        return None
    if isinstance(value, str):
        m = _PHONE_RE.search(value)
        if not m:
            return None
        digits = re.sub(r"\D", "", m.group(0))
        if not 7 <= len(digits) <= 15:
            return None
        return f"+{digits}" if m.group(0).strip().startswith("+") else digits
    if isinstance(value, list):
        for item in value:
            phone = _extract_phone(item)
            if phone:
                return phone
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower().replace("_", "") in _PHONE_KEYS:
                phone = _extract_phone(item)
                if phone:
                    return phone
    return None


async def create_backfill_job(
    db: AsyncSession, team_id: uuid.UUID, influencer_ids: list[uuid.UUID]
) -> EmailDigJob:
    if not influencer_ids:
        raise BadRequestException("请先勾选需要补邮箱的达人")
    if len(influencer_ids) > MAX_BATCH:
        raise BadRequestException(f"单次最多 {MAX_BATCH} 位，请分批提交")

    result = await db.execute(
        select(Influencer).where(Influencer.id.in_(influencer_ids), Influencer.team_id == team_id)
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
        # Prefer a woto-linked account (has external_id → no search cost).
        current = platforms_by_influencer.get(platform.influencer_id)
        if current is None or (platform.data_provider == "woto" and current.data_provider != "woto"):
            platforms_by_influencer[platform.influencer_id] = platform

    rows: list[dict] = []
    for influencer_id in influencer_ids:
        influencer = influencers.get(influencer_id)
        if not influencer:
            continue
        platform = platforms_by_influencer.get(influencer_id)
        if not platform:
            rows.append(
                {"influencer_id": str(influencer_id), "entry": influencer.name, "status": "no-platform"}
            )
            continue
        rows.append(
            {
                "influencer_id": str(influencer_id),
                "entry": platform.username,
                "platform": platform.platform.value,
                "handle": platform.username,
                "external_id": platform.external_id if platform.data_provider == "woto" else None,
                "status": "pending",
            }
        )

    if not rows:
        raise BadRequestException("勾选的达人不存在或没有平台账号")

    job = EmailDigJob(
        team_id=team_id,
        status=EmailDigJobStatus.queued,
        mode="woto",
        default_platform="tiktok",
        input_count=len(rows),
        results=rows,
    )
    db.add(job)
    await db.flush()
    return job


async def _resolve_channel_uid(db, client, job, row) -> str | None:
    """Stored woto external_id, else one billed NAME search matched by username."""
    if row.get("external_id"):
        return str(row["external_id"])
    handle = row.get("handle") or ""
    platform = row["platform"]
    body = woto_service.build_search_payload(
        {"search_type": "NAME", "blogger_name": handle}, page_num=1, page_size=10
    )
    payload = await client.search_bloggers(platform, body)
    await woto_pricing_service.record_usage(
        db,
        team_id=job.team_id,
        operation=WotoBillingOperation.influencer_search,
        platform=platform,
        dedupe_key=f"backfill-search:{platform}:{handle.lower()}",
        unit_count=1,
        description="Woto bloggerSearch (email backfill)",
        metadata={"job_id": str(job.id), "handle": handle},
    )
    candidates = woto_service._blogger_list(payload)
    for item in candidates:
        username = str(
            item.get("username") or item.get("bloggerName") or item.get("channelName") or ""
        ).strip().lstrip("@")
        if username.lower() == handle.lower():
            uid = item.get("channelUid") or item.get("channel_uid") or item.get("uid") or item.get("id")
            return str(uid) if uid else None
    return None


async def _backfill_row(db: AsyncSession, client, job: EmailDigJob, row: dict) -> None:
    influencer = await db.get(Influencer, uuid.UUID(row["influencer_id"]))
    if influencer is None or influencer.team_id != job.team_id:
        row.update(status="unresolved", applied="missing")
        return

    channel_uid = await _resolve_channel_uid(db, client, job, row)
    if not channel_uid:
        row.update(status="not-in-woto", emails=[], phones=[], applied="not-in-woto")
        return

    contact_payload = await client.blogger_contact(row["platform"], channel_uid)
    contact_data = contact_payload.get("data")
    email = woto_service._extract_email(contact_data)
    phone = _extract_phone(contact_data)
    if email:
        # Same billing rule as the manual woto-refresh: unlock is charged only
        # when Woto actually returned an email.
        await woto_pricing_service.record_usage(
            db,
            team_id=job.team_id,
            operation=WotoBillingOperation.contact_email,
            platform=row["platform"],
            dedupe_key=channel_uid,
            unit_count=1,
            description="Woto bloggerContactByChannelUid (email backfill)",
            metadata={"job_id": str(job.id), "influencer_id": row["influencer_id"]},
        )

    updated = False
    if email and not influencer.email:
        influencer.email = email
        influencer.email_verified = False
        influencer.email_source = "woto"
        updated = True
    if phone and not influencer.phone:
        influencer.phone = phone
        influencer.phone_source = "woto"
        updated = True
    if email or phone:
        influencer.email_dig_status = "found"
        influencer.email_dig_at = datetime.now(timezone.utc)

    # Remember the woto link so future refreshes skip the search step.
    platform_result = await db.execute(
        select(InfluencerPlatform).where(
            InfluencerPlatform.influencer_id == influencer.id,
            InfluencerPlatform.platform == Platform(row["platform"]),
        )
    )
    platform_record = platform_result.scalars().first()
    if platform_record and not platform_record.external_id:
        platform_record.external_id = channel_uid
        platform_record.data_provider = platform_record.data_provider or "woto"

    row.update(
        status="found" if (email or phone) else "no-email",
        emails=[email] if email else [],
        phones=[phone] if phone else [],
        applied="updated" if updated else ("has-email" if email else "no-email"),
    )


async def run_backfill_job(job_id: uuid.UUID) -> None:
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
            cfg = await woto_service.get_team_woto_config(db, job.team_id)
            async with woto_service._make_client(cfg) as client:
                # Sequential on purpose: every call is billed and rate-limited.
                for row in rows:
                    if row.get("status") == "no-platform":
                        row["applied"] = "no-platform"
                    else:
                        try:
                            await _backfill_row(db, client, job, row)
                        except WotoAPIError as exc:
                            row.update(status="error", applied="error", error=str(exc))
                    job.processed_count += 1
                    job.results = rows
                    flag_modified(job, "results")
                    await db.commit()

            job.found_count = sum(1 for row in rows if row.get("emails"))
            job.phone_found_count = sum(1 for row in rows if row.get("phones"))
            job.updated_count = sum(1 for row in rows if row.get("applied") == "updated")
            job.resolved_count = sum(
                1 for row in rows if row.get("status") not in ("no-platform", "not-in-woto", "unresolved")
            )
            job.status = EmailDigJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — job must record any failure (incl. WotoConfigurationError)
            await db.rollback()
            job.status = EmailDigJobStatus.failed
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
