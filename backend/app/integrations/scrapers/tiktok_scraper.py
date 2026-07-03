"""
TikTok public profile scraper using Playwright.

Searches hashtag pages to discover creators and extracts public profile data.
Rate-limited with random delays to avoid detection.
"""
import asyncio
import logging
import random
import re
from typing import Any

from app.integrations.scrapers.base import InfluencerScraper

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _random_delay(min_s: float = 2.0, max_s: float = 5.0) -> float:
    return random.uniform(min_s, max_s)


class TikTokScraper(InfluencerScraper):
    """Scrape TikTok hashtag pages to discover supplement influencers."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        """
        Search TikTok by hashtag and return creator profiles.
        query: hashtag without '#' (e.g. 'supplements', 'proteinpowder')
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        results: list[dict] = []
        hashtag = query.lstrip("#")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = await context.new_page()

            try:
                url = f"https://www.tiktok.com/tag/{hashtag}"
                logger.info(f"Fetching TikTok hashtag page: {url}")
                await page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                await asyncio.sleep(_random_delay(3, 6))

                # Collect creator links from the hashtag video feed
                creator_links = await page.eval_on_selector_all(
                    "a[href*='/@']",
                    "els => [...new Set(els.map(e => e.href))].filter(h => h.includes('/@') && !h.includes('/tag/'))",
                )

                unique_usernames: list[str] = []
                for link in creator_links:
                    match = re.search(r"/@([^/?]+)", link)
                    if match:
                        username = match.group(1)
                        if username not in unique_usernames:
                            unique_usernames.append(username)
                    if len(unique_usernames) >= limit:
                        break

                logger.info(f"Found {len(unique_usernames)} unique creators for #{hashtag}")

                for username in unique_usernames[:limit]:
                    try:
                        profile = await self.get_profile(username)
                        if profile:
                            profile["source_hashtag"] = f"#{hashtag}"
                            results.append(profile)
                        await asyncio.sleep(_random_delay(2, 4))
                    except Exception as exc:
                        logger.warning(f"Failed to scrape @{username}: {exc}")
                        continue

            except Exception as exc:
                logger.error(f"TikTok hashtag scrape failed for #{hashtag}: {exc}")
            finally:
                await browser.close()

        return results

    async def get_profile(self, username: str) -> dict[str, Any]:
        """Fetch a single TikTok profile page and extract public stats."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            page = await context.new_page()
            result: dict[str, Any] = {}

            try:
                url = f"https://www.tiktok.com/@{username}"
                await page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                await asyncio.sleep(_random_delay(2, 4))

                # Try to extract from __UNIVERSAL_DATA__ JSON blob (more reliable than DOM parsing)
                data_json = await page.evaluate("""
                    () => {
                        try {
                            const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
                            return el ? el.textContent : null;
                        } catch { return null; }
                    }
                """)

                followers = None
                following = None
                likes = None
                bio = None
                display_name = username
                avatar_url = None

                if data_json:
                    try:
                        import json
                        data = json.loads(data_json)
                        user_detail = (
                            data
                            .get("__DEFAULT_SCOPE__", {})
                            .get("webapp.user-detail", {})
                            .get("userInfo", {})
                        )
                        user_info = user_detail.get("user", {})
                        stats = user_detail.get("stats", {})

                        display_name = user_info.get("nickname", username)
                        bio = user_info.get("signature", "")
                        avatar_url = user_info.get("avatarMedium") or user_info.get("avatarThumb")
                        followers = stats.get("followerCount")
                        following = stats.get("followingCount")
                        likes = stats.get("heartCount") or stats.get("diggCount")
                    except Exception:
                        pass

                # Fallback: read from meta tags
                if not followers:
                    meta_desc = await page.get_attribute('meta[name="description"]', "content") or ""
                    follower_match = re.search(r"([\d.,]+[KMB]?)\s*Followers", meta_desc, re.IGNORECASE)
                    if follower_match:
                        followers = _parse_count(follower_match.group(1))

                email = self.extract_email_sync(bio or "")

                result = {
                    "username": username,
                    "display_name": display_name,
                    "platform": "tiktok",
                    "profile_url": f"https://www.tiktok.com/@{username}",
                    "followers": followers,
                    "following": following,
                    "total_likes": likes,
                    "bio": bio,
                    "avatar_url": avatar_url,
                    "email": email,
                    "engagement_rate": _estimate_engagement(followers, likes),
                }

            except Exception as exc:
                logger.warning(f"get_profile failed for @{username}: {exc}")
            finally:
                await browser.close()

        return result

    async def extract_email(self, profile_data: dict) -> str | None:
        return self.extract_email_sync(profile_data.get("bio", "") or "")

    def extract_email_sync(self, text: str) -> str | None:
        match = EMAIL_RE.search(text)
        return match.group(0) if match else None


def _parse_count(value: str) -> int | None:
    """Convert '1.2M' → 1200000, '34.5K' → 34500, etc."""
    value = value.replace(",", "").strip()
    try:
        if value.upper().endswith("B"):
            return int(float(value[:-1]) * 1_000_000_000)
        if value.upper().endswith("M"):
            return int(float(value[:-1]) * 1_000_000)
        if value.upper().endswith("K"):
            return int(float(value[:-1]) * 1_000)
        return int(float(value))
    except (ValueError, IndexError):
        return None


def _estimate_engagement(followers: int | None, likes: int | None) -> float | None:
    """Rough engagement estimate: total likes / (followers * assumed_post_count)."""
    if not followers or not likes or followers == 0:
        return None
    assumed_posts = 50
    return round((likes / (followers * assumed_posts)) * 100, 2)
