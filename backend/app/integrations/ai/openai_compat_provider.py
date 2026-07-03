"""Generic OpenAI-compatible provider.

Works with any service that exposes the OpenAI Chat Completions API:
OpenAI, DeepSeek, Mistral, Groq, Gemini (compat), Perplexity, xAI, Cohere,
Qwen/DashScope, Moonshot, Zhipu GLM, Tencent Hunyuan, Doubao, and many more.
"""

import json
import logging
import re

from openai import AsyncOpenAI

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


class OpenAICompatibleProvider(AIProvider):
    """Wraps any OpenAI-compatible Chat Completions endpoint."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.client = AsyncOpenAI(
            api_key=api_key or "placeholder",  # Ollama and some local providers ignore the key
            base_url=base_url,
        )
        self.model = model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Parse JSON from a model response, handling markdown code blocks."""
        # Strip ```json ... ``` or ``` ... ``` wrappers
        cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Fallback: find the outermost {...}
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from response: {text[:300]}")

    async def _call(self, system: str, user_message: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1024,
        )
        text = response.choices[0].message.content or ""
        return self._extract_json(text)

    async def ping(self) -> str:
        """Minimal connectivity test. Returns a short text response."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            max_tokens=16,
        )
        return (response.choices[0].message.content or "").strip()

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    async def compose_email(
        self, influencer_profile: dict, campaign_brief: str, template: str | None = None
    ) -> dict:
        template_section = (
            f"**Base Template (personalize this):**\n{template}" if template else ""
        )
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
        user_msg = ANALYZE_CONTENT_USER.format(
            profile=json.dumps(profile_data, indent=2)
        )
        return await self._call(ANALYZE_CONTENT_SYSTEM, user_msg)

    async def convert_template(self, raw_subject: str, raw_body: str) -> dict:
        user_msg = CONVERT_TEMPLATE_USER.format(subject=raw_subject, body=raw_body)
        return await self._call(CONVERT_TEMPLATE_SYSTEM, user_msg)
