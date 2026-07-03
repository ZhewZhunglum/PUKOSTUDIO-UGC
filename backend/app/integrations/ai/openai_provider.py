import json
import logging

from openai import AsyncOpenAI

from app.config import settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.prompts.email_composer import (
    ANALYZE_CONTENT_SYSTEM,
    ANALYZE_CONTENT_USER,
    CLASSIFY_REPLY_SYSTEM,
    CLASSIFY_REPLY_USER,
    COMPOSE_EMAIL_SYSTEM,
    COMPOSE_EMAIL_USER,
    CONVERT_TEMPLATE_SYSTEM,
    CONVERT_TEMPLATE_USER,
    DRAFT_REPLY_SYSTEM,
    DRAFT_REPLY_USER,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"

    async def _call(self, system: str, user_message: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
        text = response.choices[0].message.content
        return json.loads(text)

    async def compose_email(
        self, influencer_profile: dict, campaign_brief: str, template: str | None = None
    ) -> dict:
        template_section = f"**Base Template (personalize this):**\n{template}" if template else ""
        user_msg = COMPOSE_EMAIL_USER.format(
            profile=json.dumps(influencer_profile, indent=2),
            brief=campaign_brief,
            template_section=template_section,
        )
        return await self._call(COMPOSE_EMAIL_SYSTEM, user_msg)

    async def classify_reply(self, email_thread: list[dict]) -> dict:
        thread_text = self._format_thread(email_thread)
        user_msg = CLASSIFY_REPLY_USER.format(thread=thread_text)
        return await self._call(CLASSIFY_REPLY_SYSTEM, user_msg)

    async def draft_reply(
        self,
        email_thread: list[dict],
        intent: str,
        guidelines: str = "",
        playbook: dict | None = None,
    ) -> dict:
        thread_text = self._format_thread(email_thread)
        user_msg = DRAFT_REPLY_USER.format(
            thread=thread_text,
            intent=intent,
            playbook=json.dumps(playbook or {}, indent=2),
            guidelines=guidelines or "No specific guidelines.",
        )
        return await self._call(DRAFT_REPLY_SYSTEM, user_msg)

    async def analyze_content(self, profile_data: dict) -> dict:
        user_msg = ANALYZE_CONTENT_USER.format(profile=json.dumps(profile_data, indent=2))
        return await self._call(ANALYZE_CONTENT_SYSTEM, user_msg)

    async def convert_template(self, raw_subject: str, raw_body: str) -> dict:
        user_msg = CONVERT_TEMPLATE_USER.format(subject=raw_subject, body=raw_body)
        return await self._call(CONVERT_TEMPLATE_SYSTEM, user_msg)
