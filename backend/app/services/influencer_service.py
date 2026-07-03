import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.pagination import PaginationParams, paginate
from app.integrations.woto import WotoAPIError, WotoConfigurationError
from app.models.influencer import (
    Influencer,
    InfluencerPlatform,
    InfluencerStatus,
    Platform,
    Tag,
    influencer_tags,
)
from app.schemas.influencer import InfluencerCreate, InfluencerUpdate

CRM_TAGS: dict[str, tuple[str, str]] = {
    "special_attention": ("特别关注", "#f59e0b"),
    "favorite": ("已收藏", "#2563eb"),
    "recommend": ("推荐红人", "#10b981"),
    "blacklist": ("拉黑红人", "#ef4444"),
}

CRM_STATUS_ACTIONS: dict[str, InfluencerStatus] = {
    "mark_contacted": InfluencerStatus.contacted,
    "mark_replied": InfluencerStatus.replied,
    "mark_negotiating": InfluencerStatus.negotiating,
    "mark_signed": InfluencerStatus.signed,
    "mark_rejected": InfluencerStatus.rejected,
    "blacklist": InfluencerStatus.blacklisted,
    "restore": InfluencerStatus.new,
}


async def list_influencers(
    db: AsyncSession,
    team_id: uuid.UUID,
    params: PaginationParams,
    search: str | None = None,
    status: str | None = None,
    niche: str | None = None,
    platform: str | None = None,
    source: str | None = None,
    data_provider: str | None = None,
    has_email: bool | None = None,
    synced_after: datetime | None = None,
    tag_id: uuid.UUID | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> dict:
    query = (
        select(Influencer)
        .where(Influencer.team_id == team_id)
        .options(selectinload(Influencer.platforms), selectinload(Influencer.tags))
    )

    if search:
        query = query.where(
            or_(
                Influencer.name.ilike(f"%{search}%"),
                Influencer.email.ilike(f"%{search}%"),
            )
        )

    if status:
        query = query.where(Influencer.status == status)

    if niche:
        query = query.where(Influencer.niche == niche)

    if source:
        query = query.where(Influencer.source == source)

    if has_email is True:
        query = query.where(Influencer.email.is_not(None), Influencer.email != "")
    elif has_email is False:
        query = query.where(or_(Influencer.email.is_(None), Influencer.email == ""))

    if tag_id:
        query = query.join(influencer_tags).where(influencer_tags.c.tag_id == tag_id)

    if platform or min_followers or max_followers or data_provider or synced_after:
        query = query.join(InfluencerPlatform)
        if platform:
            query = query.where(InfluencerPlatform.platform == platform)
        if data_provider:
            query = query.where(InfluencerPlatform.data_provider == data_provider)
        if synced_after:
            query = query.where(InfluencerPlatform.last_synced_at >= synced_after)
        if min_followers:
            query = query.where(InfluencerPlatform.followers >= min_followers)
        if max_followers:
            query = query.where(InfluencerPlatform.followers <= max_followers)

    normalized_sort = sort_by or "gmt_create"
    normalized_order = (sort_order or "desc").lower()
    if normalized_sort in {"fans_num", "view_volume_avg_60d", "interactive_rate_60d"}:
        metric_map = {
            "fans_num": InfluencerPlatform.followers,
            "view_volume_avg_60d": InfluencerPlatform.avg_views,
            "interactive_rate_60d": InfluencerPlatform.engagement_rate,
        }
        metric_subquery = (
            select(
                InfluencerPlatform.influencer_id,
                func.max(metric_map[normalized_sort]).label("sort_value"),
            )
            .where(InfluencerPlatform.team_id == team_id)
            .group_by(InfluencerPlatform.influencer_id)
            .subquery()
        )
        query = query.outerjoin(
            metric_subquery,
            metric_subquery.c.influencer_id == Influencer.id,
        )
        sort_expression = metric_subquery.c.sort_value
    elif normalized_sort in {"gmt_modify", "latest_send_time"}:
        sort_expression = Influencer.updated_at
    else:
        sort_expression = Influencer.created_at

    direction = asc if normalized_order == "asc" else desc
    query = query.order_by(direction(sort_expression).nullslast(), Influencer.created_at.desc())

    return await paginate(db, query, params)


async def get_influencer(db: AsyncSession, influencer_id: uuid.UUID, team_id: uuid.UUID) -> Influencer:
    result = await db.execute(
        select(Influencer)
        .where(Influencer.id == influencer_id, Influencer.team_id == team_id)
        .options(selectinload(Influencer.platforms), selectinload(Influencer.tags))
    )
    influencer = result.scalar_one_or_none()
    if not influencer:
        raise NotFoundException("Influencer not found")
    return influencer


async def create_influencer(
    db: AsyncSession, team_id: uuid.UUID, data: InfluencerCreate
) -> Influencer:
    influencer = Influencer(
        team_id=team_id,
        name=data.name,
        email=data.email,
        niche=data.niche,
        country=data.country,
        notes=data.notes,
        source=data.source,
    )
    db.add(influencer)
    await db.flush()

    # Add platforms
    for p in data.platforms:
        platform = InfluencerPlatform(
            team_id=team_id,
            influencer_id=influencer.id,
            platform=Platform(p.platform),
            data_provider=p.data_provider,
            external_id=p.external_id,
            username=p.username,
            profile_url=p.profile_url,
            followers=p.followers,
            engagement_rate=p.engagement_rate,
            avg_views=p.avg_views,
        )
        db.add(platform)

    # Add tags
    if data.tag_ids:
        result = await db.execute(select(Tag).where(Tag.id.in_(data.tag_ids)))
        tags = result.scalars().all()
        influencer.tags = list(tags)

    await db.flush()
    return await get_influencer(db, influencer.id, team_id)


async def update_influencer(
    db: AsyncSession, influencer_id: uuid.UUID, team_id: uuid.UUID, data: InfluencerUpdate
) -> Influencer:
    influencer = await get_influencer(db, influencer_id, team_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "tag_ids" and value is not None:
            result = await db.execute(select(Tag).where(Tag.id.in_(value)))
            influencer.tags = list(result.scalars().all())
        elif field == "platforms" and value is not None:
            await db.execute(
                delete(InfluencerPlatform).where(
                    InfluencerPlatform.influencer_id == influencer.id
                )
            )
            for platform_data in value:
                platform_name = platform_data.get("platform")
                username = platform_data.get("username")
                if not platform_name or not username:
                    continue
                db.add(
                    InfluencerPlatform(
                        team_id=team_id,
                        influencer_id=influencer.id,
                        platform=Platform(platform_name),
                        data_provider=platform_data.get("data_provider"),
                        external_id=platform_data.get("external_id"),
                        username=username,
                        profile_url=platform_data.get("profile_url"),
                        followers=platform_data.get("followers"),
                        engagement_rate=platform_data.get("engagement_rate"),
                        avg_views=platform_data.get("avg_views"),
                    )
                )
        elif field == "status" and value is not None:
            setattr(influencer, field, InfluencerStatus(value))
        elif field not in {"tag_ids", "platforms"}:
            setattr(influencer, field, value)

    await db.flush()
    return await get_influencer(db, influencer_id, team_id)


async def delete_influencer(db: AsyncSession, influencer_id: uuid.UUID, team_id: uuid.UUID) -> None:
    influencer = await get_influencer(db, influencer_id, team_id)
    await db.delete(influencer)


async def get_influencer_emails(
    db: AsyncSession, influencer_id: uuid.UUID, team_id: uuid.UUID
):
    from app.services.email_sending_service import get_influencer_emails as list_emails

    await get_influencer(db, influencer_id, team_id)
    return await list_emails(db, influencer_id, team_id)


async def _ensure_tag(db: AsyncSession, team_id: uuid.UUID, name: str, color: str) -> Tag:
    result = await db.execute(select(Tag).where(Tag.team_id == team_id, Tag.name == name))
    tag = result.scalar_one_or_none()
    if tag:
        if not tag.color:
            tag.color = color
        return tag
    tag = Tag(team_id=team_id, name=name, color=color)
    db.add(tag)
    await db.flush()
    return tag


async def apply_crm_action(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    team_id: uuid.UUID,
    action: str,
    note: str | None = None,
) -> Influencer:
    influencer = await get_influencer(db, influencer_id, team_id)

    if action in CRM_STATUS_ACTIONS:
        influencer.status = CRM_STATUS_ACTIONS[action]

    if action in CRM_TAGS:
        tag_name, tag_color = CRM_TAGS[action]
        tag = await _ensure_tag(db, team_id, tag_name, tag_color)
        if all(existing.id != tag.id for existing in influencer.tags):
            influencer.tags.append(tag)

    if action == "append_note" or note:
        cleaned_note = (note or "").strip()
        if cleaned_note:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            entry = f"[{timestamp}] {cleaned_note}"
            influencer.notes = f"{influencer.notes}\n{entry}" if influencer.notes else entry

    if action not in {*CRM_STATUS_ACTIONS.keys(), *CRM_TAGS.keys(), "append_note"}:
        raise BadRequestException("Unsupported influencer CRM action")

    await db.flush()
    return await get_influencer(db, influencer_id, team_id)


async def refresh_influencer_from_woto(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    team_id: uuid.UUID,
) -> Influencer:
    influencer = await get_influencer(db, influencer_id, team_id)
    woto_platform = next(
        (
            platform
            for platform in influencer.platforms
            if platform.data_provider == "woto" and platform.external_id
        ),
        None,
    )
    if not woto_platform:
        raise BadRequestException("该达人没有可用于 Woto 刷新的 external_id")

    platform_value = woto_platform.platform.value
    channel_uid = str(woto_platform.external_id)
    raw_search = {}
    if isinstance(woto_platform.raw_data, dict) and isinstance(
        woto_platform.raw_data.get("search"),
        dict,
    ):
        raw_search = dict(woto_platform.raw_data["search"])
    raw_search.update(
        {
            "channelUid": channel_uid,
            "username": woto_platform.username,
            "nickname": influencer.name,
            "link": woto_platform.profile_url,
        }
    )

    try:
        from app.models.woto import WotoBillingOperation
        from app.services import woto_pricing_service, woto_service

        cfg = await woto_service.get_team_woto_config(db, team_id)
        async with woto_service._make_client(cfg) as client:
            detail_payload = await client.blogger_detail(platform_value, channel_uid)
            detail_data = detail_payload.get("data")
            if not isinstance(detail_data, dict):
                detail_data = {}

            await woto_pricing_service.record_usage(
                db,
                team_id=team_id,
                operation=WotoBillingOperation.influencer_detail,
                platform=platform_value,
                dedupe_key=channel_uid,
                unit_count=1,
                description="Woto bloggerDetail manual refresh",
                metadata={"channel_uid": channel_uid, "influencer_id": str(influencer_id)},
            )

            contact_payload = await client.blogger_contact(platform_value, channel_uid)
            contact_data = contact_payload.get("data")
            if woto_service._extract_email(contact_data):
                await woto_pricing_service.record_usage(
                    db,
                    team_id=team_id,
                    operation=WotoBillingOperation.contact_email,
                    platform=platform_value,
                    dedupe_key=channel_uid,
                    unit_count=1,
                    description="Woto bloggerContactByChannelUid manual unlock",
                    metadata={"channel_uid": channel_uid, "influencer_id": str(influencer_id)},
                )
    except WotoConfigurationError as exc:
        raise BadRequestException(str(exc)) from exc
    except WotoAPIError as exc:
        raise BadRequestException(str(exc)) from exc

    candidate = woto_service.normalize_candidate(
        platform_value,
        raw_search,
        detail=detail_data,
        contact=contact_data,
    )
    if not candidate:
        raise BadRequestException("Woto 返回数据无法归一化为本地达人")

    refreshed, _ = await woto_service.upsert_woto_candidate(db, team_id, candidate)
    await db.flush()
    return await get_influencer(db, refreshed.id, team_id)


async def get_crm_summary(db: AsyncSession, team_id: uuid.UUID) -> dict:
    total = (
        await db.execute(select(func.count()).select_from(Influencer).where(Influencer.team_id == team_id))
    ).scalar() or 0
    has_email = (
        await db.execute(
            select(func.count())
            .select_from(Influencer)
            .where(
                Influencer.team_id == team_id,
                Influencer.email.is_not(None),
                Influencer.email != "",
            )
        )
    ).scalar() or 0
    woto_count = (
        await db.execute(
            select(func.count())
            .select_from(Influencer)
            .where(Influencer.team_id == team_id, Influencer.source == "woto")
        )
    ).scalar() or 0

    status_rows = await db.execute(
        select(Influencer.status, func.count())
        .where(Influencer.team_id == team_id)
        .group_by(Influencer.status)
    )
    tag_rows = await db.execute(
        select(Tag.name, func.count(influencer_tags.c.influencer_id))
        .join(influencer_tags, influencer_tags.c.tag_id == Tag.id)
        .where(Tag.team_id == team_id, Tag.name.in_([name for name, _ in CRM_TAGS.values()]))
        .group_by(Tag.name)
    )
    return {
        "total": int(total),
        "has_email": int(has_email),
        "woto": int(woto_count),
        "by_status": {str(status.value if hasattr(status, "value") else status): int(count) for status, count in status_rows.all()},
        "by_tag": {name: int(count) for name, count in tag_rows.all()},
    }


async def bulk_tag_influencers(
    db: AsyncSession, team_id: uuid.UUID, influencer_ids: list[uuid.UUID], tag_ids: list[uuid.UUID]
) -> int:
    result = await db.execute(select(Tag).where(Tag.id.in_(tag_ids), Tag.team_id == team_id))
    tags = list(result.scalars().all())

    count = 0
    for inf_id in influencer_ids:
        try:
            influencer = await get_influencer(db, inf_id, team_id)
            existing_tag_ids = {t.id for t in influencer.tags}
            for tag in tags:
                if tag.id not in existing_tag_ids:
                    influencer.tags.append(tag)
            count += 1
        except NotFoundException:
            continue

    return count


async def import_influencers_from_rows(
    db: AsyncSession, team_id: uuid.UUID, rows: list[dict]
) -> dict:
    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows):
        try:
            name = row.get("name", "").strip()
            email = row.get("email", "").strip() or None

            if not name:
                errors.append(f"Row {i + 1}: Missing name")
                skipped += 1
                continue

            # Check duplicate by email
            if email:
                existing = await db.execute(
                    select(Influencer).where(
                        Influencer.email == email, Influencer.team_id == team_id
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

            influencer = Influencer(
                team_id=team_id,
                name=name,
                email=email,
                niche=row.get("niche", "").strip() or None,
                country=row.get("country", "US").strip() or "US",
                source="csv_import",
            )
            db.add(influencer)
            await db.flush()

            # Add platform if provided
            platform_name = row.get("platform", "").strip().lower()
            username = row.get("username", "").strip()
            if platform_name and username and platform_name in ("tiktok", "instagram", "youtube"):
                followers_str = row.get("followers", "")
                followers = int(followers_str) if followers_str and str(followers_str).isdigit() else None
                avg_views_str = row.get("avg_views", "")
                avg_views = int(avg_views_str) if avg_views_str and str(avg_views_str).isdigit() else None
                engagement_rate_str = row.get("engagement_rate", "")
                try:
                    engagement_rate = (
                        float(engagement_rate_str)
                        if str(engagement_rate_str).strip()
                        else None
                    )
                except ValueError:
                    engagement_rate = None

                platform = InfluencerPlatform(
                    team_id=team_id,
                    influencer_id=influencer.id,
                    platform=Platform(platform_name),
                    username=username,
                    profile_url=row.get("profile_url", "").strip() or None,
                    followers=followers,
                    engagement_rate=engagement_rate,
                    avg_views=avg_views,
                )
                db.add(platform)

            imported += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: {str(e)}")
            skipped += 1

    return {"total_rows": len(rows), "imported": imported, "skipped": skipped, "errors": errors}
