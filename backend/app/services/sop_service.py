import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.ai import CampaignAIPlaybook
from app.models.campaign import Campaign
from app.models.influencer import Influencer

SOP_SOURCE_TITLE = "NF工作室-海外达人合作 SOP手册"
SOP_SOURCE_UPDATED_AT = "2026-04-30"

SOP_MODULES = [
    {
        "id": "competitor_analysis",
        "title": "竞品分析",
        "output": "4步法 + AI提示词",
        "system_area": "Campaign Brief / AI Playbook",
    },
    {
        "id": "strategy_planning",
        "title": "策略规划",
        "output": "目标倒推 + 预算公式",
        "system_area": "Campaign Planning",
    },
    {
        "id": "discovery",
        "title": "达人发现",
        "output": "工具矩阵 + 关键词 + 初筛",
        "system_area": "Influencer Discovery",
    },
    {
        "id": "screening",
        "title": "达人筛选",
        "output": "二筛标准 + 分层体系",
        "system_area": "Influencer Scoring",
    },
    {
        "id": "outreach",
        "title": "建联谈判",
        "output": "邮件模板 + 3套砍价话术 + Brief",
        "system_area": "Inbox AI / Templates",
    },
    {
        "id": "contract",
        "title": "合同签署",
        "output": "检查清单 + 合规要点",
        "system_area": "Compliance",
    },
    {
        "id": "content_review",
        "title": "内容审核",
        "output": "结构公式 + 三轮审核 SOP",
        "system_area": "Creative Review",
    },
    {
        "id": "publishing",
        "title": "发布推广",
        "output": "最佳时段 + Spark Ads 放量策略",
        "system_area": "Publishing",
    },
    {
        "id": "analytics",
        "title": "数据复盘",
        "output": "三维指标 + 达人评级",
        "system_area": "Analytics",
    },
]

PRICING_BENCHMARKS = [
    {
        "tier": "C / Nano",
        "follower_range": "<10K",
        "tiktok": "Product seeding / $50-200",
        "instagram_reels": "$100-300",
        "youtube": "$200-500",
        "collaboration_model": "Seeding or affiliate first",
    },
    {
        "tier": "B / Micro",
        "follower_range": "10K-100K",
        "tiktok": "$200-1,000",
        "instagram_reels": "$500-2,000",
        "youtube": "$500-3,000",
        "collaboration_model": "Integration / seeding / paid UGC",
    },
    {
        "tier": "A / Mid",
        "follower_range": "100K-500K",
        "tiktok": "$1,000-5,000",
        "instagram_reels": "$2,000-8,000",
        "youtube": "$3,000-10,000",
        "collaboration_model": "Dedicated content",
    },
    {
        "tier": "S / Macro",
        "follower_range": "500K+",
        "tiktok": "$5,000-20,000+",
        "instagram_reels": "$8,000-30,000+",
        "youtube": "$10,000-50,000+",
        "collaboration_model": "Deep custom / long-term contract",
    },
]

PLATFORM_GUIDES = [
    {
        "platform": "TikTok",
        "content_formats": "Short video, 15-60s",
        "strength": "Fast reach and trend amplification",
        "ideal_creators": "Young, creative, high-energy creators",
        "best_posting_window_utc": "Tue-Thu 11:00-13:00 UTC",
        "amplification_note": "If engagement is >5%, test Spark Ads with $50-100 for 24-48h.",
    },
    {
        "platform": "Instagram",
        "content_formats": "Reels, Story, carousel/photo",
        "strength": "Trust and conversion quality",
        "ideal_creators": "Lifestyle and aesthetic-led creators",
        "best_posting_window_utc": "Wed-Fri 18:00-21:00 UTC",
        "amplification_note": "Repurpose strong short videos into Reels and Stories.",
    },
    {
        "platform": "YouTube",
        "content_formats": "Long video, 8-15min",
        "strength": "Deep review and search long-tail",
        "ideal_creators": "Professional reviewers and educational creators",
        "best_posting_window_utc": "Thu-Fri 14:00-16:00 UTC",
        "amplification_note": "Cut high-performing long videos into Shorts and ad assets.",
    },
]

SCREENING_RULES = [
    {
        "title": "近期更新",
        "description": "15天内有新内容；超过15天未更新视为不活跃，需要人工复核。",
        "severity": "medium",
    },
    {
        "title": "互动率",
        "description": "内容互动率目标 >=5%；低于3%通常说明内容或受众质量有风险。",
        "severity": "high",
    },
    {
        "title": "受众匹配",
        "description": "目标国家受众占比建议 >=60%，核心市场太少时不应直接入组。",
        "severity": "high",
    },
    {
        "title": "品牌历史",
        "description": "确认没有正在进行的竞品排他合作。",
        "severity": "high",
    },
    {
        "title": "报价合理",
        "description": "以 TTCM 或同类报价为基准，严重超预算时进入谈判或降级。",
        "severity": "medium",
    },
]

COMPLIANCE_RULES = [
    {
        "title": "FTC / US",
        "description": "付费、寄样或 affiliate 合作都应显眼标注 #ad 或 #sponsored。",
        "severity": "high",
    },
    {
        "title": "GDPR / EU",
        "description": "收集用户数据或追踪转化时需要明确同意与可解释用途。",
        "severity": "high",
    },
    {
        "title": "ASA / UK",
        "description": "广告内容必须真实可证，不写无法证明的效果承诺。",
        "severity": "high",
    },
    {
        "title": "中东 / SEA",
        "description": "注意宗教、文化、语言和着装禁忌，必要时走本地化审核。",
        "severity": "medium",
    },
]

NEGOTIATION_SCRIPTS = [
    {
        "title": "长期合作法",
        "description": "适合优质达人：强调 Q3/Q4 长期合作、早鸟新品、更高费率和品牌露出。",
        "severity": None,
    },
    {
        "title": "打包价法",
        "description": "适合一次谈多条内容：询问多平台、多条素材的 package best rate。",
        "severity": None,
    },
    {
        "title": "成功案例法",
        "description": "适合同量级达人：用同类达人曝光/互动结果和可接受价格区间做锚点。",
        "severity": None,
    },
]

REVIEW_CHECKLIST = [
    "核心卖点是否清晰传达",
    "品牌露出是否自然，避免硬广感",
    "#ad / #sponsored 是否正确标注",
    "CTA 是否明确且有效",
    "画面与音频质量是否达标",
    "无竞品出镜或不当内容",
    "时长是否符合 Brief 要求",
]

PERFORMANCE_METRICS = [
    {
        "title": "曝光层",
        "description": "播放量、Reach、Impression、完播率。",
        "severity": None,
    },
    {
        "title": "互动层",
        "description": "点赞率、评论率、分享率、互动率；互动率 <3% 需要复盘内容质量。",
        "severity": "medium",
    },
    {
        "title": "转化层",
        "description": "CTR、加购量、ROI/ROAS、CPE；CPE 超均值50%需复盘投放。",
        "severity": "medium",
    },
]

SOP_PLAYBOOK_DEFAULTS = {
    "enabled": True,
    "tone": "friendly, specific, concise, and collaborative",
    "language": "English",
    "pricing_rules": "\n".join(
        [
            "Use TTCM or recent comparable deals as the source of truth.",
            "Reference ranges: Nano <10K = product seeding or $50-200 TikTok; Micro 10K-100K = $200-1,000 TikTok; Mid 100K-500K = $1,000-5,000 TikTok; Macro 500K+ = $5,000-20,000+ TikTok.",
            "If a quote is above budget, ask for a package rate or propose seeding + affiliate + performance upside.",
        ]
    ),
    "negotiation_limits": "\n".join(
        [
            "Never approve rates above the configured budget without human review.",
            "Use long-term partnership, bundle pricing, or comparable case framing before rejecting.",
            "Ask for deliverables, usage rights, timeline, and platform before discussing final price.",
        ]
    ),
    "prohibited_claims": "\n".join(
        [
            "Do not make unverified health, treatment, weight-loss, FDA-approved, or guaranteed-result claims.",
            "Do not promise exclusivity, permanent usage rights, whitelisting, or paid media spend unless configured.",
        ]
    ),
    "reply_guidelines": "\n".join(
        [
            "Answer the creator's question first, then move the collaboration one step forward.",
            "For negotiation, keep the relationship warm and ask for concrete package options.",
            "For interested replies, confirm deliverables, timeline, shipping/sample details, and next steps.",
        ]
    ),
    "campaign_objectives": "Define up to 3 campaign objectives: awareness, content assets, conversion, or affiliate sales.",
    "target_audience": "Specify age, gender, location, interests, pain points, and purchase trigger.",
    "key_messages": "List up to 3 key messages or differentiators that must appear in the creator brief.",
    "content_dos": "Natural product integration; show real usage scenario; strong first 3 seconds; clear CTA.",
    "content_donts": "No competitor product in frame; no unsupported claims; no missing disclosure; no off-brand visuals.",
    "required_hashtags": "#ad or #sponsored when compensation, samples, or affiliate links are involved.",
    "disclosure_requirements": "FTC/ASA style disclosure must be clear, visible, and near the sponsored message.",
    "payment_terms": "Record amount, currency, payment milestone, and channel before contract approval.",
    "usage_rights": "Clarify content usage period, paid media permission, whitelisting/Spark Ads, and editing rights.",
    "approval_process": "R1 ops review -> R2 ops/lead review -> R3 brand owner final approval.",
    "contract_required": True,
    "content_review_checklist": "\n".join(REVIEW_CHECKLIST),
    "posting_guidance": "\n".join(
        [
            "TikTok: Tue-Thu 11:00-13:00 UTC.",
            "Instagram: Wed-Fri 18:00-21:00 UTC.",
            "YouTube: Thu-Fri 14:00-16:00 UTC.",
            "Always adapt to the creator's own audience activity data.",
        ]
    ),
    "performance_kpis": "Track impressions/reach, engagement rate, CTR, add-to-cart, ROI/ROAS, CPE, and creator cooperation quality.",
    "competitor_notes": "Summarize 3 competitors, their content hooks, weak points, creator matrix, and Top 10 content patterns.",
}


def get_sop_playbook() -> dict:
    return {
        "source_title": SOP_SOURCE_TITLE,
        "source_updated_at": SOP_SOURCE_UPDATED_AT,
        "operating_principle": "找对博主 -> 说清需求 -> 管好过程 -> 拿到结果",
        "modules": SOP_MODULES,
        "pricing_benchmarks": PRICING_BENCHMARKS,
        "platform_guides": PLATFORM_GUIDES,
        "screening_rules": SCREENING_RULES,
        "compliance_rules": COMPLIANCE_RULES,
        "negotiation_scripts": NEGOTIATION_SCRIPTS,
        "review_checklist": REVIEW_CHECKLIST,
        "performance_metrics": PERFORMANCE_METRICS,
    }


def _primary_platform(influencer: Influencer):
    if not influencer.platforms:
        return None
    return max(
        influencer.platforms,
        key=lambda platform: platform.followers or platform.avg_views or 0,
    )


def _tier_for_followers(followers: int | None) -> tuple[str, str]:
    if followers is None:
        return "unknown", "待补数据"
    if followers >= 500_000:
        return "S", "S / Macro 50W+"
    if followers >= 100_000:
        return "A", "A / Mid 10-50W"
    if followers >= 10_000:
        return "B", "B / Micro 1-10W"
    return "C", "C / Nano <1W"


def score_influencer(influencer: Influencer) -> dict:
    platform = _primary_platform(influencer)
    followers = platform.followers if platform else None
    engagement_rate = platform.engagement_rate if platform else None
    tier, tier_label = _tier_for_followers(followers)
    flags: list[str] = []
    strengths: list[str] = []
    next_steps: list[str] = []
    score = 0

    if influencer.email:
        score += 20
        strengths.append("Has email contact")
    else:
        flags.append("Missing email; use DM first or enrich contact info")
        next_steps.append("Find Email / DM / agency contact before campaign enrollment")

    if platform:
        score += 20
        strengths.append(f"Has {platform.platform.value} profile data")
    else:
        flags.append("Missing platform profile")
        next_steps.append("Add TikTok/Instagram/YouTube profile before scoring")

    if followers is not None:
        score += 15
        strengths.append(f"Follower tier: {tier_label}")
    else:
        flags.append("Missing follower count")
        next_steps.append("Add follower count to estimate tier and budget")

    if engagement_rate is None:
        flags.append("Missing engagement rate; SOP requires >=5% as a healthy line")
        next_steps.append("Validate engagement with Nox/Upfluence or recent post metrics")
    elif engagement_rate >= 5:
        score += 25
        strengths.append("Engagement rate meets SOP healthy line >=5%")
    elif engagement_rate >= 3:
        score += 12
        flags.append("Engagement rate is between 3% and 5%; review content manually")
    else:
        flags.append("Engagement rate <3%; content or audience quality may be weak")
        next_steps.append("Do not enroll until recent content quality is reviewed")

    if influencer.niche:
        score += 10
        strengths.append("Has niche/category")
    else:
        flags.append("Missing niche/category")

    if influencer.country:
        score += 10
    else:
        flags.append("Missing market/country; target audience match cannot be verified")
        next_steps.append("Confirm target country audience share, ideally >=60%")

    if score >= 75 and not any("Engagement rate <3%" in flag for flag in flags):
        recommendation = "ready_for_outreach"
    elif score >= 50:
        recommendation = "needs_review"
    else:
        recommendation = "skip_or_research"

    if not next_steps:
        next_steps.append("Enroll in a matching campaign and personalize the first outreach")

    return {
        "influencer_id": influencer.id,
        "tier": tier,
        "tier_label": tier_label,
        "readiness_score": min(score, 100),
        "recommendation": recommendation,
        "flags": flags,
        "strengths": strengths,
        "next_steps": next_steps,
    }


async def get_influencer_score(
    db: AsyncSession,
    influencer_id: uuid.UUID,
    team_id: uuid.UUID,
) -> dict:
    from app.services.influencer_service import get_influencer

    influencer = await get_influencer(db, influencer_id, team_id)
    return score_influencer(influencer)


async def apply_sop_defaults_to_playbook(
    db: AsyncSession,
    campaign_id: uuid.UUID,
    team_id: uuid.UUID,
    overwrite: bool = False,
) -> CampaignAIPlaybook:
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.team_id == team_id)
    )
    campaign = campaign_result.scalar_one_or_none()
    if not campaign:
        raise NotFoundException("Campaign not found")

    playbook_result = await db.execute(
        select(CampaignAIPlaybook).where(CampaignAIPlaybook.campaign_id == campaign_id)
    )
    playbook = playbook_result.scalar_one_or_none()
    if not playbook:
        playbook = CampaignAIPlaybook(campaign_id=campaign_id)
        db.add(playbook)

    for field, value in SOP_PLAYBOOK_DEFAULTS.items():
        current_value = getattr(playbook, field)
        if overwrite or current_value in (None, "", False):
            setattr(playbook, field, value)

    if not playbook.product_name:
        playbook.product_name = campaign.name
    if not playbook.product_description and campaign.description:
        playbook.product_description = campaign.description

    await db.flush()
    return playbook
