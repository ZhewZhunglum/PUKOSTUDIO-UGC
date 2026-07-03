"""AI provider factory.

Resolution order:
  1. Explicit config dict (from team DB ai_settings)
  2. Environment variables (AI_PROVIDER, CLAUDE_API_KEY, OPENAI_API_KEY)

auth_type values:
  api_key  — standard Bearer-token auth (all OpenAI-compat providers)
  azure    — Azure OpenAI (needs azure_endpoint + api_version)
  aws      — Amazon Bedrock (needs aws_access_key_id + secret + region)

Model catalog last synced from official API docs: 2026-05-21
"""

from __future__ import annotations

from app.config import settings
from app.integrations.ai.base import AIProvider

# ---------------------------------------------------------------------------
# Provider catalog
# Each entry is returned to the frontend as-is (no secrets here).
# ---------------------------------------------------------------------------

PROVIDER_CATALOG: list[dict] = [
    # ── International ──────────────────────────────────────────────────────
    {
        "id": "claude",
        "name": "Anthropic Claude",
        "auth_type": "api_key",
        "base_url": None,
        "models": [
            # Current generation (dateless aliases, pinned snapshots)
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
            # Legacy — still available
            "claude-opus-4-6",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
        ],
        "region": "international",
        "docs": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
        "note": "使用 Anthropic 原生 SDK，无需填写 Base URL",
    },
    {
        "id": "openai",
        "name": "OpenAI GPT",
        "auth_type": "api_key",
        "base_url": "https://api.openai.com/v1",
        "models": [
            # GPT-4.1 series (April 2025)
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            # o-series reasoning models
            "o3",
            "o4-mini",
            "o3-mini",
            # GPT-4o (still widely used)
            "gpt-4o",
            "gpt-4o-mini",
        ],
        "region": "international",
        "docs": "https://platform.openai.com/docs/models",
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "auth_type": "api_key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            # Gemini 3 series (2025)
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            # Gemini 2.5 series
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            # Gemini 2.0
            "gemini-2.0-flash",
        ],
        "region": "international",
        "docs": "https://ai.google.dev/gemini-api/docs/models",
        "note": "使用 Gemini 的 OpenAI 兼容端点，API Key 从 Google AI Studio 获取",
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "auth_type": "api_key",
        "base_url": "https://api.mistral.ai/v1",
        "models": [
            "mistral-large-3",
            "mistral-medium-3.5",
            "mistral-small-4",
            "magistral-medium-1.2",
            "codestral",
            "devstral-2",
            "ministral-3-8b",
        ],
        "region": "international",
        "docs": "https://docs.mistral.ai/getting-started/models/models_overview/",
    },
    {
        "id": "cohere",
        "name": "Cohere",
        "auth_type": "api_key",
        "base_url": "https://api.cohere.com/compatibility/v1",
        "models": [
            "command-a-03-2025",
            "command-a-plus-05-2026",
            "command-a-reasoning-08-2025",
            "command-r7b-12-2024",
            "command-r-plus-08-2024",
        ],
        "region": "international",
        "docs": "https://docs.cohere.com/docs/models",
        "note": "使用 Cohere 的 OpenAI 兼容端点",
    },
    {
        "id": "ai21",
        "name": "AI21 Labs (Jamba)",
        "auth_type": "api_key",
        "base_url": "https://api.ai21.com/studio/v1",
        "models": ["jamba-large", "jamba-mini"],
        "region": "international",
        "docs": "https://docs.ai21.com",
    },
    {
        "id": "xai",
        "name": "xAI Grok",
        "auth_type": "api_key",
        "base_url": "https://api.x.ai/v1",
        "models": ["grok-4.3", "grok-3", "grok-3-mini"],
        "region": "international",
        "docs": "https://docs.x.ai/docs/models",
    },
    {
        "id": "perplexity",
        "name": "Perplexity AI",
        "auth_type": "api_key",
        "base_url": "https://api.perplexity.ai",
        "models": [
            "sonar-pro",
            "sonar",
            "sonar-reasoning-pro",
            "sonar-deep-research",
        ],
        "region": "international",
        "docs": "https://docs.perplexity.ai/guides/model-cards",
    },
    {
        "id": "together",
        "name": "Together AI",
        "auth_type": "api_key",
        "base_url": "https://api.together.xyz/v1",
        "models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen3.5-397B-A17B",
            "deepseek-ai/DeepSeek-V4-Pro",
            "moonshotai/Kimi-K2.6",
            "Qwen/Qwen3.5-9B",
            "google/gemma-4-31B-it",
        ],
        "region": "international",
        "docs": "https://docs.together.ai/docs/inference-models",
    },
    {
        "id": "groq",
        "name": "Groq",
        "auth_type": "api_key",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "qwen/qwen3-32b",
            "groq/compound",
            "groq/compound-mini",
        ],
        "region": "international",
        "docs": "https://console.groq.com/docs/models",
    },
    {
        "id": "fireworks",
        "name": "Fireworks AI",
        "auth_type": "api_key",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "models": [
            "accounts/fireworks/models/kimi-k2p6",
            "accounts/fireworks/models/deepseek-v3p2",
            "accounts/fireworks/models/qwen3-235b-a22b",
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "accounts/fireworks/models/gpt-oss-120b",
            "accounts/fireworks/models/llama-v3p1-8b-instruct",
        ],
        "region": "international",
        "docs": "https://docs.fireworks.ai/guides/recommended-models",
    },
    {
        "id": "replicate",
        "name": "Replicate",
        "auth_type": "api_key",
        "base_url": "https://openai-compat.replicate.com/v1",
        "models": [],
        "region": "international",
        "docs": "https://replicate.com/docs",
        "note": "模型名格式：owner/model-name（如 meta/meta-llama-3-70b-instruct）",
    },
    {
        "id": "huggingface",
        "name": "Hugging Face",
        "auth_type": "api_key",
        "base_url": "https://api-inference.huggingface.co/v1",
        "models": [],
        "region": "international",
        "docs": "https://huggingface.co/docs/api-inference",
        "note": "模型名填写 HF model id，如 mistralai/Mistral-7B-Instruct-v0.3",
    },
    {
        "id": "bedrock",
        "name": "Amazon Bedrock",
        "auth_type": "aws",
        "base_url": None,
        "models": [
            # Anthropic Claude on Bedrock
            "anthropic.claude-opus-4-7",
            "anthropic.claude-sonnet-4-6",
            "anthropic.claude-haiku-4-5-20251001-v1:0",
            # Amazon Nova
            "amazon.nova-premier-v1:0",
            "amazon.nova-pro-v1:0",
            "amazon.nova-lite-v1:0",
            "amazon.nova-micro-v1:0",
            # Meta Llama 4
            "meta.llama4-scout-17b-instruct-v1:0",
            "meta.llama4-maverick-17b-instruct-v1:0",
            "meta.llama3-3-70b-instruct-v1:0",
        ],
        "region": "international",
        "docs": "https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html",
        "extra_fields": [
            {"key": "aws_region", "label": "AWS Region", "placeholder": "us-east-1", "required": True},
            {"key": "aws_access_key_id", "label": "Access Key ID", "placeholder": "AKIAIOSFODNN7EXAMPLE", "required": True},
            {"key": "aws_secret_access_key", "label": "Secret Access Key", "placeholder": "wJalrXUtnFEMI/K7MDENG/...", "type": "password", "required": True},
        ],
    },
    {
        "id": "azure",
        "name": "Azure OpenAI",
        "auth_type": "azure",
        "base_url": None,
        "models": ["gpt-4.1", "gpt-4o", "gpt-4o-mini", "o3", "o4-mini"],
        "region": "international",
        "docs": "https://learn.microsoft.com/azure/ai-services/openai",
        "extra_fields": [
            {"key": "azure_endpoint", "label": "Azure Endpoint", "placeholder": "https://myresource.openai.azure.com", "required": True},
            {"key": "api_version", "label": "API Version", "placeholder": "2025-01-01-preview", "default": "2025-01-01-preview", "required": True},
        ],
        "note": "模型名填写 Azure AI Foundry 中的 deployment 名称",
    },
    {
        "id": "vertex",
        "name": "Google Vertex AI",
        "auth_type": "api_key",
        "base_url": "",
        "models": [
            "gemini-3.5-flash",
            "gemini-2.5-pro-002",
            "gemini-2.5-flash-002",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ],
        "region": "international",
        "docs": "https://cloud.google.com/vertex-ai/docs",
        "note": "Base URL 格式：https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{location}/endpoints/openapi",
    },
    # ── Domestic ───────────────────────────────────────────────────────────
    {
        "id": "ernie",
        "name": "百度文心 (ERNIE)",
        "auth_type": "api_key",
        "base_url": "https://qianfan.baidubce.com/v2",
        "models": [
            "ernie-4.5-8k",
            "ernie-4.5-turbo-8k",
            "ernie-4.0-8k",
            "ernie-3.5-128k",
            "ernie-speed-128k",
            "ernie-lite-8k",
        ],
        "region": "domestic",
        "docs": "https://cloud.baidu.com/doc/WENXINWORKSHOP",
        "note": "使用千帆平台「应用API Key」作为 API Key",
    },
    {
        "id": "qwen",
        "name": "阿里通义千问 (Qwen)",
        "auth_type": "api_key",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            # Qwen 3.6 series (2025)
            "qwen3.6-max-preview",
            "qwen3.6-plus",
            "qwen3.6-flash",
            # Stable aliases
            "qwen-max",
            "qwen-plus",
            "qwen-turbo",
            "qwen-long",
        ],
        "region": "domestic",
        "docs": "https://help.aliyun.com/zh/model-studio/use-qwen-by-calling-api",
    },
    {
        "id": "spark",
        "name": "讯飞星火",
        "auth_type": "api_key",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "models": [
            "4.0Ultra",
            "max-32k",
            "pro-128k",
            "generalv3.5",
            "generalv3",
            "lite",
        ],
        "region": "domestic",
        "docs": "https://www.xfyun.cn/doc/spark",
        "note": "API Key 格式：{APIKey}:{APISecret}（拼接后填入）",
    },
    {
        "id": "zhipu",
        "name": "智谱 GLM",
        "auth_type": "api_key",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            "glm-5.1",
            "glm-5",
            "glm-5-turbo",
            "glm-4.7",
            "glm-4.7-flashx",
            "glm-4.6",
            "glm-4.5-air",
        ],
        "region": "domestic",
        "docs": "https://docs.bigmodel.cn/cn/guide/start/model-overview",
    },
    {
        "id": "moonshot",
        "name": "月之暗面 (Kimi)",
        "auth_type": "api_key",
        "base_url": "https://api.moonshot.cn/v1",
        "models": [
            # Kimi K2 series (2025)
            "kimi-k2.6",
            "kimi-k2.5",
            "kimi-k2-thinking",
            # Moonshot stable
            "moonshot-v1-auto",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ],
        "region": "domestic",
        "docs": "https://platform.kimi.com/docs/api/chat",
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "auth_type": "api_key",
        "base_url": "https://api.minimax.chat/v1",
        "models": ["MiniMax-Text-01", "abab6.5s-chat"],
        "region": "domestic",
        "docs": "https://platform.minimaxi.com/document/guides",
    },
    {
        "id": "baichuan",
        "name": "百川智能",
        "auth_type": "api_key",
        "base_url": "https://api.baichuan-ai.com/v1",
        "models": ["Baichuan4-Turbo", "Baichuan4-Air", "Baichuan4", "Baichuan3-Turbo"],
        "region": "domestic",
        "docs": "https://platform.baichuan-ai.com/docs",
    },
    {
        "id": "yi",
        "name": "零一万物 (Yi)",
        "auth_type": "api_key",
        "base_url": "https://api.lingyiwanwu.com/v1",
        "models": ["yi-lightning", "yi-large-turbo", "yi-medium"],
        "region": "domestic",
        "docs": "https://platform.lingyiwanwu.com/docs",
    },
    {
        "id": "deepseek",
        "name": "深度求索 (DeepSeek)",
        "auth_type": "api_key",
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            # V4 series (current, 2025)
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            # Legacy aliases (deprecated 2026-07-24 but still functional)
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "region": "domestic",
        "docs": "https://api-docs.deepseek.com/",
    },
    {
        "id": "hunyuan",
        "name": "腾讯混元",
        "auth_type": "api_key",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "models": [
            "hunyuan-t1-latest",
            "hunyuan-turbos-latest",
            "hunyuan-a13b",
            "hunyuan-lite",
        ],
        "region": "domestic",
        "docs": "https://cloud.tencent.com/document/product/1729",
    },
    {
        "id": "doubao",
        "name": "字节豆包",
        "auth_type": "api_key",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": [],
        "region": "domestic",
        "docs": "https://www.volcengine.com/docs/82379",
        "note": "模型名填写火山引擎控制台「推理接入点」的 endpoint_id",
    },
    {
        "id": "sensenova",
        "name": "商汤日日新",
        "auth_type": "api_key",
        "base_url": "https://api.sensenova.cn/compatible-mode/v1",
        "models": ["SenseChat-5", "SenseChat-Turbo", "SenseChat-5-Cantonese"],
        "region": "domestic",
        "docs": "https://platform.sensenova.cn/doc",
    },
    {
        "id": "step",
        "name": "阶跃星辰 (Step)",
        "auth_type": "api_key",
        "base_url": "https://api.stepfun.com/v1",
        "models": ["step-2-turbo", "step-2", "step-2-mini", "step-1-flash", "step-1-8k"],
        "region": "domestic",
        "docs": "https://platform.stepfun.com/docs",
    },
    {
        "id": "tiangong",
        "name": "天工 AI",
        "auth_type": "api_key",
        "base_url": "https://sky-api.singularity-ai.com/saas/api/v4",
        "models": ["SkyChat-MegaVerse"],
        "region": "domestic",
        "docs": "https://model.tiangong.cn/docs",
    },
    # ── Local / Custom ─────────────────────────────────────────────────────
    {
        "id": "ollama",
        "name": "Ollama (本地)",
        "auth_type": "api_key",
        "base_url": "http://localhost:11434/v1",
        "models": [],
        "region": "local",
        "docs": "https://ollama.ai",
        "note": "本地模型无需 API Key，模型名如 llama3.2、qwen2.5:7b、deepseek-r1:7b",
    },
    {
        "id": "custom",
        "name": "自定义 OpenAI 兼容 API",
        "auth_type": "api_key",
        "base_url": "",
        "models": [],
        "region": "custom",
        "docs": "",
    },
]

_CATALOG_INDEX: dict[str, dict] = {p["id"]: p for p in PROVIDER_CATALOG}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_ai_provider(config: dict | None = None) -> AIProvider:
    """Build an AIProvider from a config dict or env fallback.

    config keys:
      provider, api_key, model, base_url,
      azure_endpoint, api_version  (Azure)
      aws_region, aws_access_key_id, aws_secret_access_key  (Bedrock)
    """
    if config and config.get("provider"):
        return _build_from_config(config)

    # ── Env fallback ──────────────────────────────────────────────────────
    if settings.ai_provider == "claude":
        from app.integrations.ai.claude_provider import ClaudeProvider
        return ClaudeProvider()
    if settings.ai_provider == "openai":
        from app.integrations.ai.openai_compat_provider import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
        )
    raise ValueError(f"Unknown AI provider in env: {settings.ai_provider}")


def _build_from_config(config: dict) -> AIProvider:
    provider_id: str = config["provider"]
    api_key: str = config.get("api_key", "")
    model: str = config.get("model", "")
    catalog_entry = _CATALOG_INDEX.get(provider_id, {})
    auth_type: str = catalog_entry.get("auth_type", "api_key")

    # Override base_url: explicit config > catalog default
    base_url: str | None = config.get("base_url") or catalog_entry.get("base_url")

    if provider_id == "claude":
        from app.integrations.ai.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key or None, model=model or None)

    if auth_type == "azure":
        from app.integrations.ai.azure_provider import AzureOpenAIProvider
        return AzureOpenAIProvider(
            api_key=api_key,
            model=model,
            azure_endpoint=config.get("azure_endpoint", ""),
            api_version=config.get("api_version", "2024-02-01"),
        )

    if auth_type == "aws":
        from app.integrations.ai.bedrock_provider import BedrockProvider
        return BedrockProvider(
            model=model,
            region=config.get("aws_region", "us-east-1"),
            access_key_id=config.get("aws_access_key_id", ""),
            secret_access_key=config.get("aws_secret_access_key", ""),
        )

    # Default: OpenAI-compatible
    from app.integrations.ai.openai_compat_provider import OpenAICompatibleProvider
    return OpenAICompatibleProvider(api_key=api_key, model=model, base_url=base_url)


async def get_team_ai_provider(db, team_id) -> AIProvider:
    """Load team AI settings from DB and return the provider. Falls back to env."""
    from sqlalchemy import select

    from app.models.user import Team

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    cfg = (team.ai_settings if team else None) or {}
    return get_ai_provider(cfg if cfg.get("provider") else None)
