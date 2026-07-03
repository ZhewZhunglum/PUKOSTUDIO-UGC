from abc import ABC, abstractmethod


class InfluencerScraper(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 50) -> list[dict]:
        """Search for influencers by keyword/hashtag.

        Returns list of: {"username", "profile_url", "followers", "engagement_rate", "bio", "email"}
        """
        ...

    @abstractmethod
    async def get_profile(self, username: str) -> dict:
        """Get detailed profile information for a specific influencer."""
        ...

    @abstractmethod
    async def extract_email(self, profile_data: dict) -> str | None:
        """Extract email from profile data (bio, linked website, etc.)."""
        ...
