"""
Instagram public profile scraper using Playwright.

Navigates hashtag explore pages to find supplement creators and extracts
public profile data from the JSON embedded in the page.
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
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _random_delay(min_s: float = 2.5, max_s: float = 6.0) -> float:
    return random.uniform(min_s, max_s)


class InstagramScraper(InfluencerScraper):
    """Scrape Instagram hashtag pages to discover supplement influencers."""

    def __init__(self, headless: bool = True, timeout_ms: int = 35000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        """
        Search Instagram by hashtag and return creator profiles.
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
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            page = await context.new_page()

            try:
                url = f"https://www.instagram.com/explore/tags/{hashtag}/"
                logger.info(f"Fetching Instagram hashtag page: {url}")
                await page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                await asyncio.sleep(_random_delay(4, 7))

                # Gather post links, then extract author usernames
                post_links = await page.eval_on_selector_all(
                    "a[href*='/p/']",
                    "els => [...new Set(els.map(e => e.href))]",
                )

                unique_usernames: list[str] = []

                for post_link in post_links[:limit * 2]:
                    try:
                        await page.goto(post_link, timeout=self.timeout_ms, wait_until="domcontentloaded")
                        await asyncio.sleep(_random_delay(1.5, 3.5))

                        # Author link pattern: /<username>/
                        author_link = await page.get_attribute(
                            'a[href^="/"][href$="/"]',
                            "href",
                        )
                        if author_link:
                            username = author_link.strip("/")
                            if username and username not in unique_usernames and "/" not in username:
                                unique_usernames.append(username)
                    except Exception:
                        continue

                    if len(unique_usernames) >= limit:
                        break

                logger.info(f"Found {len(unique_usernames)} unique creators for #{hashtag}")

                for username in unique_usernames[:limit]:
                    try:
                        profile = await self.get_profile(username)
                        if profile:
                            profile["source_hashtag"] = f"#{hashtag}"
                            results.append(profile)
                        await asyncio.sleep(_random_delay(2.5, 5))
                    except Exception as exc:
                        logger.warning(f"Failed to scrape @{username}: {exc}")
                        continue

            except Exception as exc:
                logger.error(f"Instagram hashtag scrape failed for #{hashtag}: {exc}")
            finally:
                await browser.close()

        return results

    async def get_profile(self, username: str) -> dict[str, Any]:
        """Fetch a single Instagram profile and extract public stats."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            page = await context.new_page()
            result: dict[str, Any] = {}

            try:
                url = f"https://www.instagram.com/{username}/"
                await page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                await asyncio.sleep(_random_delay(2.5, 5))

                # Instagram embeds profile data in <script type="application/ld+json">
                ld_json = await page.eval_on_selector(
                    'script[type="application/ld+json"]',
                    "el => el.textContent",
                )

                followers = None
                following = None
                bio = None
                display_name = username
                avatar_url = None

                if ld_json:
                    try:
                        import json
                        data = json.loads(ld_json)
                        if isinstance(data, list):
                            data = data[0]
                        display_name = data.get("name", username)
                        bio = data.get("description", "")
                        avatar_url = data.get("image")
                        interaction_stats = data.get("interactionStatistic", [])
                        for stat in interaction_stats:
                            stat_type = stat.get("interactionType", "")
                            if "Follow" in stat_type:
                                followers = stat.get("userInteractionCount")
                    except Exception:
                        pass

                # Fallback: meta description
                if not followers:
                    meta_content = await page.get_attribute('meta[name="description"]', "content") or ""
                    m = re.search(r"([\d.,]+[KMB]?)\s*Followers", meta_content, re.IGNORECASE)
                    if m:
                        followers = _parse_count(m.group(1))
                    m2 = re.search(r"([\d.,]+[KMB]?)\s*Following", meta_content, re.IGNORECASE)
                    if m2:
                        following = _parse_count(m2.group(1))

                if not bio:
                    bio = await page.get_attribute('meta[property="og:description"]', "content") or ""

                email = self.extract_email_sync(bio)

                result = {
                    "username": username,
                    "display_name": display_name,
                    "platform": "instagram",
                    "profile_url": f"https://www.instagram.com/{username}/",
                    "followers": followers,
                    "following": following,
                    "bio": bio,
                    "avatar_url": avatar_url,
                    "email": email,
                    "engagement_rate": None,
                }

            except Exception as exc:
                logger.warning(f"Instagram get_profile failed for @{username}: {exc}")
            finally:
                await browser.close()

        return result

    async def extract_email(self, profile_data: dict) -> str | None:
        return self.extract_email_sync(profile_data.get("bio", "") or "")

    def extract_email_sync(self, text: str) -> str | None:
        match = EMAIL_RE.search(text)
        return match.group(0) if match else None


def _parse_count(value: str) -> int | None:
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
