"""
Scraper manager — unified interface for running TikTok / Instagram scrapers
and persisting discovered influencers to the database.
"""
import logging
import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

Platform = Literal["tiktok", "instagram"]

SUPPLEMENT_HASHTAGS: dict[str, list[str]] = {
    "tiktok": [
        "supplements", "proteinsupplement", "proteinpowder", "preworkout",
        "vitamins", "probiotics", "omega3", "collagen", "weightloss",
        "guthealth", "fitnessnutrition", "bodybuilding", "gymlife",
        "healthsupplement", "naturalhealth",
    ],
    "instagram": [
        "supplements", "proteinsupplements", "preworkout", "vitamins",
        "probiotics", "omega3", "collagen", "guthealth", "fitnesslife",
        "healthandwellness", "naturalhealth", "sportssupplements",
    ],
}


async def run_scrape_job(
    db: AsyncSession,
    team_id: uuid.UUID,
    platform: Platform,
    hashtag: str,
    limit: int = 30,
    niche: str | None = None,
    country: str = "US",
) -> dict:
    """
    Scrape a hashtag on the given platform, de-duplicate against existing DB,
    and insert new influencers. Returns summary stats.
    """
    from app.models.influencer import (
        Influencer,
        InfluencerPlatform,
        InfluencerStatus,
    )
    from app.models.influencer import (
        Platform as PlatformEnum,
    )

    if platform == "tiktok":
        from app.integrations.scrapers.tiktok_scraper import TikTokScraper
        scraper = TikTokScraper(headless=True)
    elif platform == "instagram":
        from app.integrations.scrapers.instagram_scraper import InstagramScraper
        scraper = InstagramScraper(headless=True)
    else:
        return {"error": f"Unsupported platform: {platform}", "discovered": 0, "inserted": 0}

    logger.info(f"[ScraperManager] Starting {platform} scrape for #{hashtag} (limit={limit})")
    raw_profiles = await scraper.search(hashtag, limit=limit)
    logger.info(f"[ScraperManager] Got {len(raw_profiles)} raw profiles")

    inserted = 0
    skipped = 0

    for profile in raw_profiles:
        username = profile.get("username", "").strip()
        if not username:
            continue

        # De-duplicate: check if a platform entry with this username already exists
        existing_platform = await db.execute(
            select(InfluencerPlatform).where(
                InfluencerPlatform.platform == PlatformEnum(platform),
                InfluencerPlatform.username == username,
            )
        )
        if existing_platform.scalar_one_or_none():
            skipped += 1
            continue

        # Create new influencer record
        display_name = profile.get("display_name") or username
        email = profile.get("email")

        influencer = Influencer(
            id=uuid.uuid4(),
            team_id=team_id,
            name=display_name,
            email=email if email else None,
            email_verified=False,
            avatar_url=profile.get("avatar_url"),
            niche=niche or "general_health",
            country=country,
            status=InfluencerStatus.new,
            source=f"scraped_{platform}",
            notes=profile.get("bio", "")[:500] if profile.get("bio") else None,
        )
        db.add(influencer)
        await db.flush()

        platform_record = InfluencerPlatform(
            id=uuid.uuid4(),
            team_id=team_id,
            influencer_id=influencer.id,
            platform=PlatformEnum(platform),
            username=username,
            profile_url=profile.get("profile_url", ""),
            followers=profile.get("followers"),
            engagement_rate=profile.get("engagement_rate"),
            avg_views=profile.get("avg_views"),
            raw_data={
                "bio": profile.get("bio"),
                "following": profile.get("following"),
                "total_likes": profile.get("total_likes"),
                "source_hashtag": profile.get("source_hashtag"),
            },
        )
        db.add(platform_record)
        inserted += 1

    return {
        "platform": platform,
        "hashtag": hashtag,
        "discovered": len(raw_profiles),
        "inserted": inserted,
        "skipped": skipped,
    }


def get_suggested_hashtags(platform: Platform) -> list[str]:
    return SUPPLEMENT_HASHTAGS.get(platform, [])
