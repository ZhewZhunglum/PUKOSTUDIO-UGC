import re
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.database import async_session
from app.core.exceptions import BadRequestException, NotFoundException
from app.integrations.woto import WotoAPIError, WotoClient, WotoConfigurationError
from app.models.campaign import Campaign, CampaignStatus
from app.models.influencer import Influencer, InfluencerPlatform, InfluencerStatus, Platform
from app.models.woto import WotoBillingOperation, WotoSyncJob, WotoSyncJobStatus
from app.schemas.woto import WotoDictionaryItem, WotoQuotaResponse, WotoSyncJobCreate
from app.services import campaign_service, woto_pricing_service

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass
class WotoInfluencerCandidate:
    platform: str
    external_id: str | None
    username: str
    name: str
    profile_url: str | None
    avatar_url: str | None
    country: str | None
    followers: int | None
    engagement_rate: float | None
    avg_views: int | None
    email: str | None
    has_email_hint: bool | None
    tags: list[Any]
    raw_data: dict[str, Any]


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", ""))
    except (TypeError, ValueError):
        return None


def _first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _country_code(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) == 2 and text.isalpha():
        return text.upper()
    return None


def _extract_email(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        match = EMAIL_RE.search(value)
        return match.group(0).lower() if match else None
    if isinstance(value, list):
        for item in value:
            email = _extract_email(item)
            if email:
                return email
    if isinstance(value, dict):
        for key in ("email", "mail", "contact", "value"):
            email = _extract_email(value.get(key))
            if email:
                return email
    return None


def build_search_payload(data: dict[str, Any], page_num: int, page_size: int) -> dict[str, Any]:
    search_type = data.get("search_type") or "KEYWORD"
    keyword = (data.get("keyword") or "").strip()
    blogger_name = (data.get("blogger_name") or "").strip()
    exclude_keywords = [k.strip() for k in data.get("exclude_keywords", []) if k.strip()]

    payload: dict[str, Any] = {
        "searchType": search_type,
        "searchSort": data.get("sort") or "FANS_NUM",
        "sortOrder": data.get("sort_order") or "desc",
        "pageSize": page_size,
        "pageNum": page_num,
    }

    if search_type == "NAME":
        payload["bloggerName"] = blogger_name or keyword
    else:
        advanced_keywords = []
        if keyword:
            # Woto treats each advancedKeywordList item independently (OR logic).
            # A single entry like "supplement/energy/collagen" is matched as a
            # literal string and returns zero results — split each term into
            # its own entry.
            terms = [t.strip() for t in re.split(r"[/,]+", keyword) if t.strip()]
            for term in terms or [keyword]:
                advanced_keywords.append({"value": term, "exclude": False})
        advanced_keywords.extend({"value": kw, "exclude": True} for kw in exclude_keywords)
        if advanced_keywords:
            payload["advancedKeywordList"] = advanced_keywords

    region_ids = [str(region_id) for region_id in data.get("region_ids", []) if str(region_id)]
    if region_ids:
        payload["regionList"] = [{"id": region_id} for region_id in region_ids]

    category_ids = [str(category_id) for category_id in data.get("category_ids", []) if str(category_id)]
    if category_ids:
        payload["blogCateIds"] = category_ids

    field_map = {
        "min_followers": "minFansNum",
        "max_followers": "maxFansNum",
        "min_engagement_rate": "minInteractiveRate",
        "max_engagement_rate": "maxInteractiveRate",
    }
    for source_key, target_key in field_map.items():
        if data.get(source_key) is not None:
            payload[target_key] = data[source_key]

    if data.get("has_email") is not None:
        payload["hasEmail"] = data["has_email"]

    min_views = data.get("min_avg_views")
    max_views = data.get("max_avg_views")
    if min_views is not None or max_views is not None:
        payload["viewVolumeCombination"] = {
            "min": min_views or 0,
            "max": max_views,
            "type": "AVG",
            "excludeTop": False,
            "range": "N30",
        }

    return payload


def normalize_candidate(
    platform: str,
    search_item: dict[str, Any],
    *,
    detail: dict[str, Any] | None = None,
    contact: Any = None,
) -> WotoInfluencerCandidate | None:
    raw_detail = detail or {}
    merged = {**search_item, **raw_detail}
    external_id = _first_present(merged, ["channelUid", "channel_uid", "uid", "id"])
    username = _first_present(
        merged,
        ["username", "bloggerName", "channelName", "uniqueId", "nickname"],
    )
    if not username and external_id:
        username = str(external_id)
    if not username:
        return None

    name = _first_present(merged, ["nickname", "displayName", "name", "username"]) or username
    email = _extract_email(contact) or _extract_email(merged)
    tags = merged.get("tagList") or merged.get("tags") or merged.get("blogCateList") or []
    if not isinstance(tags, list):
        tags = [tags]

    has_email_hint = merged.get("hasEmail")
    if isinstance(has_email_hint, str):
        has_email_hint = has_email_hint.lower() == "true"
    elif has_email_hint is not None:
        has_email_hint = bool(has_email_hint)

    # Prefer detail-level metrics over search-level ones when available
    avg_views = _to_int(
        _first_present(merged, ["viewVolumeAvg60d", "viewVolumeAvg30d", "viewAvg", "avgViews", "avg_views", "viewsAvg"])
    )
    engagement_rate = _to_float(
        _first_present(merged, ["interactiveRate60d", "interactiveRate", "engagementRate", "avgInteractiveRate"])
    )

    # Collect all structured Woto metrics into raw_data for frontend display
    _METRIC_MAP: list[tuple[str, str]] = [
        ("total_star", "totalStar"),
        ("region_zh", "regionZh"),
        ("region_cover", "regionCover"),
        ("like_avg", "likeAvg"),
        ("like_avg_60d", "likeVolumeAvg60d"),
        ("view_avg_15d", "viewVolumeAvg15d"),
        ("view_avg_30d", "viewVolumeAvg30d"),
        ("view_avg_60d", "viewVolumeAvg60d"),
        ("view_avg_15n", "viewVolumeAvg15n"),
        ("view_avg_30n", "viewVolumeAvg30n"),
        ("interactive_rate_60d", "interactiveRate60d"),
        ("interactive_rate_30n_all", "interactiveRate30nAll"),
        ("interactive_rate_90d_post", "interactiveRate90dPost"),
        ("content_num", "contentNum"),
        ("latest_publish_date", "latestPublishDate"),
        ("is_tk_union", "isTkUnion"),
        ("gmv_30d", "gmv30d"),
        ("biz_count", "bizCount"),
        ("has_amazon_tag", "hasAmazonTag"),
    ]
    woto_metrics: dict[str, Any] = {}
    for dest_key, src_key in _METRIC_MAP:
        val = merged.get(src_key)
        if val is not None:
            woto_metrics[dest_key] = val

    # Category info (only populated when detail was fetched)
    cate_ids: list[Any] = raw_detail.get("blogCateIds") or []
    cate_names: list[Any] = raw_detail.get("blogCateNames") or []
    if cate_ids:
        woto_metrics["cate_ids"] = cate_ids
    if cate_names:
        woto_metrics["cate_names"] = cate_names

    # Audience demographics (only populated when detail was fetched)
    for src_key, dest_key in [("fansAge", "fans_age"), ("fansSex", "fans_sex"), ("fansRegion", "fans_region")]:
        val = raw_detail.get(src_key)
        if val:
            woto_metrics[dest_key] = val

    raw_data: dict[str, Any] = {
        "provider": "woto",
        "search": search_item,
        "detail": raw_detail,
        "contact": contact,
        "tags": tags,
        **woto_metrics,
    }

    return WotoInfluencerCandidate(
        platform=platform,
        external_id=str(external_id) if external_id else None,
        username=str(username).strip().lstrip("@"),
        name=str(name).strip(),
        profile_url=_first_present(merged, ["link", "profileUrl", "profile_url", "url"]),
        avatar_url=_first_present(merged, ["avatar", "avatarUrl", "avatar_url"]),
        country=_country_code(_first_present(merged, ["region", "country", "countryCode"])),
        followers=_to_int(_first_present(merged, ["fansNum", "followers", "followerCount", "subscribers"])),
        engagement_rate=engagement_rate,
        avg_views=avg_views,
        email=email,
        has_email_hint=has_email_hint,
        tags=tags,
        raw_data=raw_data,
    )


def _blogger_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        values = payload.get("bloggerList") or payload.get("list") or payload.get("records") or []
        return values if isinstance(values, list) else []
    return []


def _has_next_page(data: dict[str, Any], current_count: int, page_size: int) -> bool:
    payload = data.get("data") or {}
    if not isinstance(payload, dict):
        return False
    if payload.get("hasNextPage") is not None:
        return bool(payload.get("hasNextPage"))
    return current_count >= page_size


WOTO_PRODUCTION_BASE_URL = "https://api.wotohub.com/api-gateway"


async def get_team_woto_config(db: AsyncSession, team_id: uuid.UUID) -> dict:
    """Return effective Woto config for a team, falling back to global settings."""
    from app.models.user import Team  # avoid circular import at module level

    team = await db.get(Team, team_id)
    raw = (team.woto_settings or {}) if team else {}
    api_key = raw.get("api_key") or settings.woto_api_key
    use_sandbox = bool(raw.get("use_sandbox", False))
    production_base_url = raw.get("production_base_url") or settings.woto_api_base_url or WOTO_PRODUCTION_BASE_URL
    sandbox_base_url = raw.get("sandbox_base_url") or ""
    effective_base_url = sandbox_base_url if (use_sandbox and sandbox_base_url) else production_base_url
    return {
        "api_key": api_key,
        "effective_base_url": effective_base_url,
        "use_sandbox": use_sandbox,
        "production_base_url": production_base_url,
        "sandbox_base_url": sandbox_base_url,
    }


def _make_client(cfg: dict) -> WotoClient:
    return WotoClient(api_key=cfg["api_key"] or None, base_url=cfg["effective_base_url"])


async def query_quota(db: AsyncSession | None = None, team_id: uuid.UUID | None = None) -> WotoQuotaResponse:
    if db is not None and team_id is not None:
        cfg = await get_team_woto_config(db, team_id)
        client_ctx = _make_client(cfg)
    else:
        client_ctx = WotoClient()
    async with client_ctx as client:
        payload = await client.query_quota()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return WotoQuotaResponse(remain_quota=_to_int(data.get("remainQuota")), raw=payload)


async def list_dictionary(
    dict_type_code: str,
    db: AsyncSession | None = None,
    team_id: uuid.UUID | None = None,
) -> list[WotoDictionaryItem]:
    if db is not None and team_id is not None:
        cfg = await get_team_woto_config(db, team_id)
        client_ctx = _make_client(cfg)
    else:
        client_ctx = WotoClient()
    async with client_ctx as client:
        payload = await client.list_dict_by_code(dict_type_code)
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        rows = []
    return [
        WotoDictionaryItem(
            id=row.get("id"),
            dict_code=row.get("dictCode"),
            dict_value=row.get("dictValue"),
            dict_type_code=row.get("dictTypeCode"),
            raw=row,
        )
        for row in rows
        if isinstance(row, dict)
    ]


async def create_sync_job(
    db: AsyncSession,
    team_id: uuid.UUID,
    data: WotoSyncJobCreate,
) -> WotoSyncJob:
    query = data.model_dump(mode="json")
    if data.search_type == "KEYWORD" and not data.keyword:
        raise BadRequestException("关键词搜索需要填写 keyword")
    if data.search_type == "NAME" and not (data.blogger_name or data.keyword):
        raise BadRequestException("达人名搜索需要填写 blogger_name")
    if data.campaign_id:
        campaign = await campaign_service.get_campaign(db, data.campaign_id, team_id)
        if campaign.status not in (CampaignStatus.draft, CampaignStatus.paused):
            raise BadRequestException("只能把 Woto 达人自动入组到 draft 或 paused 活动")

    estimate = await woto_pricing_service.estimate_sync_cost(db, team_id, data)
    job = WotoSyncJob(
        team_id=team_id,
        campaign_id=data.campaign_id,
        platform=data.platform,
        query=query,
        status=WotoSyncJobStatus.queued,
        estimated_cost_cny=estimate.estimated_total_cny,
        warning_messages=[],
    )
    db.add(job)
    await db.flush()
    return job


async def list_sync_jobs(db: AsyncSession, team_id: uuid.UUID, limit: int = 20) -> list[WotoSyncJob]:
    result = await db.execute(
        select(WotoSyncJob)
        .where(WotoSyncJob.team_id == team_id)
        .order_by(WotoSyncJob.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_sync_job(db: AsyncSession, team_id: uuid.UUID, job_id: uuid.UUID) -> WotoSyncJob:
    result = await db.execute(
        select(WotoSyncJob).where(WotoSyncJob.id == job_id, WotoSyncJob.team_id == team_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundException("Woto sync job not found")
    return job


async def _find_existing_platform(
    db: AsyncSession,
    team_id: uuid.UUID,
    candidate: WotoInfluencerCandidate,
) -> InfluencerPlatform | None:
    platform_enum = Platform(candidate.platform)
    if candidate.external_id:
        result = await db.execute(
            select(InfluencerPlatform)
            .join(Influencer, Influencer.id == InfluencerPlatform.influencer_id)
            .where(
                Influencer.team_id == team_id,
                InfluencerPlatform.platform == platform_enum,
                InfluencerPlatform.data_provider == "woto",
                InfluencerPlatform.external_id == candidate.external_id,
            )
            .options(selectinload(InfluencerPlatform.influencer).selectinload(Influencer.platforms))
        )
        platform_record = result.scalar_one_or_none()
        if platform_record:
            return platform_record

    conditions = []
    if candidate.username:
        conditions.append(func.lower(InfluencerPlatform.username) == candidate.username.lower())
    if candidate.profile_url:
        conditions.append(InfluencerPlatform.profile_url == candidate.profile_url)
    if not conditions:
        return None

    result = await db.execute(
        select(InfluencerPlatform)
        .join(Influencer, Influencer.id == InfluencerPlatform.influencer_id)
        .where(
            Influencer.team_id == team_id,
            InfluencerPlatform.platform == platform_enum,
            or_(*conditions),
        )
        .options(selectinload(InfluencerPlatform.influencer).selectinload(Influencer.platforms))
    )
    return result.scalars().first()


async def _find_existing_influencer_by_email(
    db: AsyncSession,
    team_id: uuid.UUID,
    email: str | None,
) -> Influencer | None:
    if not email:
        return None
    result = await db.execute(
        select(Influencer)
        .where(Influencer.team_id == team_id, func.lower(Influencer.email) == email.lower())
        .options(selectinload(Influencer.platforms))
    )
    return result.scalar_one_or_none()


async def upsert_woto_candidate(
    db: AsyncSession,
    team_id: uuid.UUID,
    candidate: WotoInfluencerCandidate,
) -> tuple[Influencer, str]:
    now = datetime.now(timezone.utc)
    platform_enum = Platform(candidate.platform)
    platform_record = await _find_existing_platform(db, team_id, candidate)
    influencer = platform_record.influencer if platform_record else None
    status = "updated" if influencer else "created"

    if influencer is None:
        influencer = await _find_existing_influencer_by_email(db, team_id, candidate.email)
        if influencer:
            status = "updated"

    influencer_is_new = influencer is None

    if influencer is None:
        influencer = Influencer(
            team_id=team_id,
            name=candidate.name,
            email=candidate.email,
            email_verified=False,
            avatar_url=candidate.avatar_url,
            country=candidate.country,
            status=InfluencerStatus.new,
            source="woto",
        )
        db.add(influencer)
        await db.flush()
    else:
        if candidate.email and not influencer.email:
            influencer.email = candidate.email
            influencer.email_verified = False
        if candidate.avatar_url and not influencer.avatar_url:
            influencer.avatar_url = candidate.avatar_url
        if candidate.country and not influencer.country:
            influencer.country = candidate.country
        if not influencer.source:
            influencer.source = "woto"

    if platform_record is None and not influencer_is_new:
        # Avoid lazy-loading influencer.platforms in an async session.
        # Query directly instead — safe because influencer already existed in DB.
        existing_result = await db.execute(
            select(InfluencerPlatform).where(
                InfluencerPlatform.influencer_id == influencer.id,
                InfluencerPlatform.platform == platform_enum,
            )
        )
        platform_record = existing_result.scalars().first()

    if platform_record is None:
        platform_record = InfluencerPlatform(
            team_id=team_id,
            influencer_id=influencer.id,
            platform=platform_enum,
            data_provider="woto",
            external_id=candidate.external_id,
            username=candidate.username,
        )
        db.add(platform_record)

    platform_record.team_id = team_id
    platform_record.data_provider = "woto"
    platform_record.external_id = candidate.external_id or platform_record.external_id
    platform_record.username = candidate.username or platform_record.username
    platform_record.profile_url = candidate.profile_url or platform_record.profile_url
    platform_record.followers = candidate.followers
    platform_record.engagement_rate = candidate.engagement_rate
    platform_record.avg_views = candidate.avg_views
    platform_record.content_topics = {
        "woto_tags": candidate.tags,
        "has_email": candidate.has_email_hint,
        "cate_names": candidate.raw_data.get("cate_names") or [],
        "cate_ids": candidate.raw_data.get("cate_ids") or [],
    }
    platform_record.raw_data = candidate.raw_data
    platform_record.last_synced_at = now

    await db.flush()
    return influencer, status


async def run_sync_job(
    job_id: uuid.UUID,
    session_factory: async_sessionmaker | None = None,
) -> None:
    """Execute a Woto sync job.

    Callers running under asyncio.run() (e.g. Celery tasks) should pass a
    NullPool-backed session_factory so concurrent invocations don't share
    asyncpg connections across event-loop boundaries.
    """
    _session = session_factory or async_session
    async with _session() as db:
        job = await db.get(WotoSyncJob, job_id)
        if not job:
            return

        job.status = WotoSyncJobStatus.running
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        job.warning_messages = []
        await db.commit()

        imported_ids: list[uuid.UUID] = []
        warnings: list[str] = []
        query = job.query or {}
        limit = min(int(query.get("limit") or settings.woto_default_sync_limit), 500)
        page_size_setting = min(max(settings.woto_page_size, 1), 50)
        processed = 0
        page_num = 1

        try:
            cfg = await get_team_woto_config(db, job.team_id)
            async with _make_client(cfg) as client:
                while processed < limit:
                    page_size = min(page_size_setting, limit - processed)
                    search_body = build_search_payload(query, page_num, page_size)
                    search_payload = await client.search_bloggers(job.platform, search_body)
                    await woto_pricing_service.record_usage(
                        db,
                        team_id=job.team_id,
                        sync_job_id=job.id,
                        operation=WotoBillingOperation.influencer_search,
                        platform=job.platform,
                        dedupe_key=f"{job.id}:search:{page_num}",
                        unit_count=1,
                        description="Woto bloggerSearch",
                        metadata={"page_num": page_num, "page_size": page_size},
                    )
                    items = _blogger_list(search_payload)
                    if not items:
                        break

                    for item in items:
                        if processed >= limit:
                            break
                        processed += 1
                        job.discovered += 1
                        if not isinstance(item, dict):
                            job.skipped_count += 1
                            continue

                        channel_uid = item.get("channelUid")
                        detail_data: dict[str, Any] | None = None
                        contact_data: Any = None

                        should_fetch_detail = query.get("fetch_detail", True)
                        if channel_uid and should_fetch_detail:
                            try:
                                detail_payload = await client.blogger_detail(job.platform, str(channel_uid))
                                await woto_pricing_service.record_usage(
                                    db,
                                    team_id=job.team_id,
                                    sync_job_id=job.id,
                                    operation=WotoBillingOperation.influencer_detail,
                                    platform=job.platform,
                                    dedupe_key=str(channel_uid),
                                    unit_count=1,
                                    description="Woto bloggerDetail",
                                    metadata={"channel_uid": str(channel_uid)},
                                )
                                raw_detail = detail_payload.get("data")
                                # Woto bloggerDetail returns data as a list[dict] on
                                # some platforms/versions — unwrap the first element.
                                if isinstance(raw_detail, list) and raw_detail:
                                    raw_detail = raw_detail[0]
                                if isinstance(raw_detail, dict):
                                    detail_data = raw_detail
                            except (WotoAPIError, WotoConfigurationError) as exc:
                                warnings.append(f"{channel_uid} 详情获取失败：{exc}")

                        if channel_uid:
                            has_email_hint = item.get("hasEmail")
                            should_fetch_contact = should_fetch_detail and query.get("enrich_contacts", True) and (
                                has_email_hint is not False
                            )
                            if should_fetch_contact:
                                try:
                                    contact_payload = await client.blogger_contact(
                                        job.platform,
                                        str(channel_uid),
                                    )
                                    contact_data = contact_payload.get("data")
                                    if _extract_email(contact_data):
                                        await woto_pricing_service.record_usage(
                                            db,
                                            team_id=job.team_id,
                                            sync_job_id=job.id,
                                            operation=WotoBillingOperation.contact_email,
                                            platform=job.platform,
                                            dedupe_key=str(channel_uid),
                                            unit_count=1,
                                            description="Woto bloggerContactByChannelUid",
                                            metadata={"channel_uid": str(channel_uid)},
                                        )
                                except (WotoAPIError, WotoConfigurationError) as exc:
                                    warnings.append(f"{channel_uid} 联系方式获取失败：{exc}")

                        candidate = normalize_candidate(
                            job.platform,
                            item,
                            detail=detail_data,
                            contact=contact_data,
                        )
                        if not candidate:
                            job.skipped_count += 1
                            continue

                        influencer, upsert_status = await upsert_woto_candidate(
                            db,
                            job.team_id,
                            candidate,
                        )
                        imported_ids.append(influencer.id)
                        if upsert_status == "created":
                            job.created_count += 1
                        else:
                            job.updated_count += 1

                    await db.flush()
                    if not _has_next_page(search_payload, len(items), page_size):
                        break
                    page_num += 1

            if job.campaign_id and imported_ids:
                unique_ids = list(dict.fromkeys(imported_ids))
                try:
                    job.enrolled_count = await campaign_service.enroll_influencers(
                        db,
                        job.campaign_id,
                        job.team_id,
                        unique_ids,
                    )
                except Exception as exc:
                    warnings.append(f"自动入组失败：{exc}")

            job.warning_messages = warnings[:100]
            await woto_pricing_service.update_sync_job_costs(db, job)
            job.status = WotoSyncJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception:
            full_tb = traceback.format_exc()
            await db.rollback()
            failed_job = await db.get(WotoSyncJob, job_id)
            if failed_job:
                failed_job.status = WotoSyncJobStatus.failed
                # Store full traceback (truncated to 4000 chars) so we can diagnose without logs
                failed_job.error_message = full_tb[:4000]
                failed_job.completed_at = datetime.now(timezone.utc)
                failed_job.warning_messages = warnings[:100]
                await woto_pricing_service.update_sync_job_costs(db, failed_job)
                await db.commit()


async def validate_woto_available(
    db: AsyncSession | None = None,
    team_id: uuid.UUID | None = None,
) -> None:
    if db is not None and team_id is not None:
        cfg = await get_team_woto_config(db, team_id)
        client_ctx = _make_client(cfg)
    else:
        client_ctx = WotoClient()
    try:
        async with client_ctx as client:
            await client.query_quota()
    except WotoConfigurationError as exc:
        raise BadRequestException(str(exc)) from exc
    except WotoAPIError as exc:
        raise BadRequestException(str(exc)) from exc


async def get_campaign_options(db: AsyncSession, team_id: uuid.UUID) -> list[Campaign]:
    result = await db.execute(
        select(Campaign)
        .where(
            Campaign.team_id == team_id,
            Campaign.status.in_([CampaignStatus.draft, CampaignStatus.paused]),
        )
        .order_by(Campaign.created_at.desc())
    )
    return list(result.scalars().all())
