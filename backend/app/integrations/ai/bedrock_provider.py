"""Amazon Bedrock provider.

Docs: https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html
Auth: AWS credentials (access_key_id + secret_access_key + region).
Requires: boto3  (pip install boto3)

Model IDs (current as of 2026-05):
  Anthropic Claude:
    anthropic.claude-opus-4-7
    anthropic.claude-sonnet-4-6
    anthropic.claude-haiku-4-5-20251001-v1:0
  Amazon Nova:
    amazon.nova-premier-v1:0
    amazon.nova-pro-v1:0
    amazon.nova-lite-v1:0
    amazon.nova-micro-v1:0
  Meta Llama:
    meta.llama4-scout-17b-instruct-v1:0
    meta.llama4-maverick-17b-instruct-v1:0
    meta.llama3-3-70b-instruct-v1:0
"""

from __future__ import annotations

import json
import logging
import re

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


def _check_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "boto3 is required for Amazon Bedrock. "
            "Install it with: pip install boto3"
        ) from exc


class BedrockProvider(AIProvider):
    """Provider for Amazon Bedrock via boto3 bedrock-runtime client."""

    def __init__(
        self,
        model: str,
        region: str = "us-east-1",
        access_key_id: str = "",
        secret_access_key: str = "",
    ):
        _check_boto3()
        import boto3

        self.model = model
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from response: {text[:300]}")

    async def _call(self, system: str, user_message: str) -> dict:
        import asyncio

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        })

        def _invoke() -> str:
            response = self.client.invoke_model(
                modelId=self.model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            # Claude-on-Bedrock response format
            if "content" in result:
                return result["content"][0]["text"]
            # Other model formats
            return result.get("outputs", [{}])[0].get("text", "")

        text = await asyncio.get_event_loop().run_in_executor(None, _invoke)
        return self._extract_json(text)

    async def ping(self) -> str:
        import asyncio

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
        })

        def _invoke() -> str:
            response = self.client.invoke_model(
                modelId=self.model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            if "content" in result:
                return result["content"][0]["text"]
            return result.get("outputs", [{}])[0].get("text", "")

        return await asyncio.get_event_loop().run_in_executor(None, _invoke)

    async def compose_email(
        self, influencer_profile: dict, campaign_brief: str, template: str | None = None
    ) -> dict:
        template_section = (
            f"**Base Template:**\n{template}" if template else ""
        )
        return await self._call(
            COMPOSE_EMAIL_SYSTEM,
            COMPOSE_EMAIL_USER.format(
                profile=json.dumps(influencer_profile, indent=2),
                brief=campaign_brief,
                template_section=template_section,
            ),
        )

    async def classify_reply(self, email_thread: list[dict]) -> dict:
        return await self._call(
            CLASSIFY_REPLY_SYSTEM,
            CLASSIFY_REPLY_USER.format(thread=self._format_thread(email_thread)),
        )

    async def draft_reply(
        self,
        email_thread: list[dict],
        intent: str,
        guidelines: str = "",
        playbook: dict | None = None,
    ) -> dict:
        return await self._call(
            DRAFT_REPLY_SYSTEM,
            DRAFT_REPLY_USER.format(
                thread=self._format_thread(email_thread),
                intent=intent,
                playbook=json.dumps(playbook or {}, indent=2),
                guidelines=guidelines or "No specific guidelines.",
            ),
        )

    async def analyze_content(self, profile_data: dict) -> dict:
        return await self._call(
            ANALYZE_CONTENT_SYSTEM,
            ANALYZE_CONTENT_USER.format(profile=json.dumps(profile_data, indent=2)),
        )

    async def convert_template(self, raw_subject: str, raw_body: str) -> dict:
        return await self._call(
            CONVERT_TEMPLATE_SYSTEM,
            CONVERT_TEMPLATE_USER.format(subject=raw_subject, body=raw_body),
        )
