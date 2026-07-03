import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.woto import WotoBillingOperation, WotoSyncJob, WotoUsageRecord
from app.schemas.woto import (
    WotoCostEstimateLine,
    WotoCostEstimateResponse,
    WotoDiscountTier,
    WotoPricingItem,
    WotoPricingTableResponse,
    WotoSyncJobCreate,
)

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class PricingRule:
    operation: WotoBillingOperation
    label: str
    platform: str
    unit_price_cny: Decimal
    unit: str
    return_count: str | None
    description: str


PRICE_RULES: tuple[PricingRule, ...] = (
    PricingRule(
        WotoBillingOperation.influencer_search,
        "红人搜索",
        "all",
        Decimal("0.50"),
        "次",
        "50 个红人",
        "按关键词、国家、粉丝量等条件筛选。",
    ),
    PricingRule(
        WotoBillingOperation.influencer_detail,
        "YouTube 红人基础数据",
        "youtube",
        Decimal("0.75"),
        "个红人",
        "1 个红人",
        "频道信息、粉丝画像、视频总表现、Woto 评分、预估 CPM 等。",
    ),
    PricingRule(
        WotoBillingOperation.influencer_detail,
        "Instagram 红人基础数据",
        "instagram",
        Decimal("1.50"),
        "个红人",
        "1 个红人",
        "基础数据、粉丝画像、平均互动率。",
    ),
    PricingRule(
        WotoBillingOperation.influencer_detail,
        "TikTok 红人基础数据",
        "tiktok",
        Decimal("1.50"),
        "个红人",
        "1 个红人",
        "基础数据、粉丝画像、视频表现、TikTok Shop 达人标记。",
    ),
    PricingRule(
        WotoBillingOperation.video_data,
        "视频数据",
        "all",
        Decimal("0.38"),
        "条视频",
        "1 条视频",
        "标题、播放量、互动率、点赞/评论量、推广品牌。",
    ),
    PricingRule(
        WotoBillingOperation.contact_email,
        "红人联系邮箱",
        "all",
        Decimal("1.50"),
        "个邮箱",
        "1 个邮箱",
        "已验证的商务邮箱或联系方式。",
    ),
    PricingRule(
        WotoBillingOperation.brand_monitoring,
        "品牌监控",
        "all",
        Decimal("1500.00"),
        "年/词",
        None,
        "开通费，不含后续数据调用；调用费按标准价另计。",
    ),
)

DISCOUNT_TIERS: tuple[tuple[int, int | None, Decimal, str], ...] = (
    (0, 10_000, Decimal("1.00"), "< 1 万，无折扣"),
    (10_000, 50_000, Decimal("0.90"), "1 万 - 5 万，9 折"),
    (50_000, 100_000, Decimal("0.80"), "5 万 - 10 万，8 折"),
    (100_000, None, Decimal("0.70"), "> 10 万，7 折起"),
)

DEDUPE_OPERATIONS = {
    WotoBillingOperation.influencer_detail,
    WotoBillingOperation.video_data,
    WotoBillingOperation.contact_email,
}


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def discount_for_call_count(call_count: int) -> Decimal:
    for min_calls, max_calls, discount_rate, _ in DISCOUNT_TIERS:
        if call_count >= min_calls and (max_calls is None or call_count < max_calls):
            return discount_rate
    return Decimal("1.00")


def get_price_rule(operation: WotoBillingOperation, platform: str | None = None) -> PricingRule:
    normalized_platform = (platform or "all").lower()
    for rule in PRICE_RULES:
        if rule.operation == operation and rule.platform == normalized_platform:
            return rule
    for rule in PRICE_RULES:
        if rule.operation == operation and rule.platform == "all":
            return rule
    raise ValueError(f"No Woto pricing rule for {operation.value}/{platform}")


def _month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def get_monthly_usage(db: AsyncSession, team_id: uuid.UUID) -> tuple[int, Decimal]:
    result = await db.execute(
        select(
            func.coalesce(func.sum(WotoUsageRecord.unit_count), 0),
            func.coalesce(func.sum(WotoUsageRecord.amount_cny), 0),
        ).where(
            WotoUsageRecord.team_id == team_id,
            WotoUsageRecord.billable.is_(True),
            WotoUsageRecord.operation != WotoBillingOperation.brand_monitoring,
            WotoUsageRecord.created_at >= _month_start(),
        )
    )
    call_count, spend = result.one()
    return int(call_count or 0), money(Decimal(str(spend or 0)))


async def get_pricing_table(db: AsyncSession, team_id: uuid.UUID) -> WotoPricingTableResponse:
    monthly_calls, monthly_spend = await get_monthly_usage(db, team_id)
    return WotoPricingTableResponse(
        valid_from="2026-05-01",
        valid_to="2026-12-31",
        rate_limit_per_minute=60,
        duplicate_policy="相同红人或视频在服务期内重复获取不计费；系统用 Woto external_id 做本地去重。",
        items=[
            WotoPricingItem(
                operation=rule.operation.value,
                label=rule.label,
                platform=rule.platform,
                unit_price_cny=rule.unit_price_cny,
                unit=rule.unit,
                return_count=rule.return_count,
                description=rule.description,
            )
            for rule in PRICE_RULES
        ],
        discount_tiers=[
            WotoDiscountTier(
                min_calls=min_calls,
                max_calls=max_calls,
                discount_rate=discount_rate,
                label=label,
            )
            for min_calls, max_calls, discount_rate, label in DISCOUNT_TIERS
        ],
        current_month_billable_calls=monthly_calls,
        current_discount_rate=discount_for_call_count(monthly_calls),
        current_month_spend_cny=monthly_spend,
    )


def _line(
    *,
    operation: WotoBillingOperation,
    platform: str,
    units: int,
    discount_rate: Decimal,
    note: str | None = None,
) -> WotoCostEstimateLine:
    rule = get_price_rule(operation, platform)
    subtotal = money(rule.unit_price_cny * Decimal(units))
    return WotoCostEstimateLine(
        operation=operation.value,
        label=rule.label,
        platform=platform,
        unit_price_cny=rule.unit_price_cny,
        units=units,
        subtotal_cny=subtotal,
        discounted_subtotal_cny=money(subtotal * discount_rate),
        note=note,
    )


async def estimate_sync_cost(
    db: AsyncSession,
    team_id: uuid.UUID,
    data: WotoSyncJobCreate,
) -> WotoCostEstimateResponse:
    monthly_calls, _ = await get_monthly_usage(db, team_id)
    discount_rate = discount_for_call_count(monthly_calls)
    page_size = min(max(settings.woto_page_size, 1), 50)
    search_units = max(1, math.ceil(data.limit / page_size))
    detail_units = data.limit if data.fetch_detail else 0
    contact_units = data.limit if data.fetch_detail and data.enrich_contacts and data.has_email is not False else 0

    lines: list[WotoCostEstimateLine] = [
        _line(
            operation=WotoBillingOperation.influencer_search,
            platform=data.platform,
            units=search_units,
            discount_rate=discount_rate,
            note="红人搜索每次最多返回 50 个红人。",
        ),
    ]
    if detail_units:
        lines.append(
            _line(
                operation=WotoBillingOperation.influencer_detail,
                platform=data.platform,
                units=detail_units,
                discount_rate=discount_rate,
                note="估算按每个返回达人获取 1 次基础数据计算。",
            )
        )
    if contact_units:
        lines.append(
            _line(
                operation=WotoBillingOperation.contact_email,
                platform=data.platform,
                units=contact_units,
                discount_rate=discount_rate,
                note="估算按每个达人最多返回 1 个邮箱计算；实际无邮箱则不记费。",
            )
        )

    subtotal = money(sum((line.subtotal_cny for line in lines), Decimal("0.00")))
    total = money(sum((line.discounted_subtotal_cny for line in lines), Decimal("0.00")))
    estimated_calls = search_units + detail_units + contact_units
    # note: contact is only possible when detail is enabled, so no double-counting
    return WotoCostEstimateResponse(
        discount_rate=discount_rate,
        monthly_billable_calls_before=monthly_calls,
        estimated_billable_calls=estimated_calls,
        estimated_subtotal_cny=subtotal,
        estimated_total_cny=total,
        lines=lines,
        notes=[
            "这是任务开始前的最高估算，实际 Woto 返回数量低于 limit 时会降低。",
            "相同红人或视频在服务期内重复获取不计费，系统会用本地用量账本把重复 external_id 记为 0 元。",
            "联系方式按已返回邮箱计费；接口无邮箱或联系方式获取失败时不会计入实际邮箱费用。",
        ],
    )


async def record_usage(
    db: AsyncSession,
    *,
    team_id: uuid.UUID,
    operation: WotoBillingOperation,
    platform: str | None = None,
    sync_job_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
    unit_count: int = 1,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> WotoUsageRecord:
    rule = get_price_rule(operation, platform)
    billable = unit_count > 0
    if billable and operation in DEDUPE_OPERATIONS and dedupe_key:
        existing = await db.execute(
            select(WotoUsageRecord.id)
            .where(
                WotoUsageRecord.team_id == team_id,
                WotoUsageRecord.operation == operation,
                WotoUsageRecord.platform == (platform or "all"),
                WotoUsageRecord.dedupe_key == dedupe_key,
                WotoUsageRecord.billable.is_(True),
            )
            .limit(1)
        )
        billable = existing.scalar_one_or_none() is None

    monthly_calls, _ = await get_monthly_usage(db, team_id)
    discount_rate = discount_for_call_count(monthly_calls)
    amount = money(rule.unit_price_cny * Decimal(unit_count) * discount_rate) if billable else Decimal("0.00")
    record = WotoUsageRecord(
        team_id=team_id,
        sync_job_id=sync_job_id,
        operation=operation,
        platform=platform or "all",
        dedupe_key=dedupe_key,
        unit_count=unit_count,
        unit_price_cny=rule.unit_price_cny,
        discount_rate=discount_rate,
        amount_cny=amount,
        billable=billable,
        description=description,
        metadata_=metadata,
    )
    db.add(record)
    await db.flush()
    return record


async def update_sync_job_costs(db: AsyncSession, job: WotoSyncJob) -> None:
    result = await db.execute(
        select(
            WotoUsageRecord.operation,
            func.coalesce(func.sum(WotoUsageRecord.unit_count), 0),
            func.coalesce(func.sum(WotoUsageRecord.amount_cny), 0),
        )
        .where(
            WotoUsageRecord.sync_job_id == job.id,
            WotoUsageRecord.billable.is_(True),
        )
        .group_by(WotoUsageRecord.operation)
    )
    search_calls = 0
    detail_calls = 0
    contact_calls = 0
    amount = Decimal("0.00")
    for operation, unit_count, subtotal in result.all():
        units = int(unit_count or 0)
        amount += Decimal(str(subtotal or 0))
        if operation == WotoBillingOperation.influencer_search:
            search_calls = units
        elif operation == WotoBillingOperation.influencer_detail:
            detail_calls = units
        elif operation == WotoBillingOperation.contact_email:
            contact_calls = units

    job.billable_search_calls = search_calls
    job.billable_detail_calls = detail_calls
    job.billable_contact_calls = contact_calls
    job.actual_cost_cny = money(amount)
