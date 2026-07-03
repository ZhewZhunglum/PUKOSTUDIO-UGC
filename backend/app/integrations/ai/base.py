from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    async def compose_email(
        self,
        influencer_profile: dict,
        campaign_brief: str,
        template: str | None = None,
    ) -> dict:
        """Generate a personalized outreach email.

        Returns: {"subject": str, "body_html": str, "body_text": str}
        """
        ...

    @abstractmethod
    async def classify_reply(self, email_thread: list[dict]) -> dict:
        """Classify the intent of an influencer's reply.

        Returns: {"intent": str, "confidence": float, "summary": str}
        Intent: interested, not_interested, question, negotiation, spam
        """
        ...

    @abstractmethod
    async def draft_reply(
        self,
        email_thread: list[dict],
        intent: str,
        guidelines: str = "",
        playbook: dict | None = None,
    ) -> dict:
        """Draft a reply based on the conversation and detected intent.

        Returns: {"subject": str, "body_html": str, "body_text": str,
        "rationale": str, "missing_context": str, "risk_level": str}
        """
        ...

    @abstractmethod
    async def analyze_content(self, profile_data: dict) -> dict:
        """Analyze an influencer's content for brand fit.

        Returns: {"topics": list, "style": str, "brand_fit_score": float, "summary": str}
        """
        ...

    @abstractmethod
    async def convert_template(self, raw_subject: str, raw_body: str) -> dict:
        """Convert plain email text into a {{variable}} template.

        Returns: {"subject": str, "body_html": str, "variables": list[str]}
        """
        ...

    @staticmethod
    def _format_thread(email_thread: list[dict]) -> str:
        """Format an email thread into a readable string for AI prompts."""
        return "\n\n".join(
            f"**From:** {m.get('from', 'Unknown')}\n**Date:** {m.get('date', '')}\n{m.get('body', '')}"
            for m in email_thread
        )
