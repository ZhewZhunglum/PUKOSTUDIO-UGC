"""
Team settings API — Woto API and AI provider configuration.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestException
from app.dependencies import get_current_user
from app.integrations.ai.factory import PROVIDER_CATALOG, get_ai_provider
from app.integrations.woto import WotoAPIError, WotoClient, WotoConfigurationError
from app.models.user import Team, User
from app.services.woto_service import WOTO_PRODUCTION_BASE_URL, get_team_woto_config

router = APIRouter()


class WotoSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, description="留空表示不修改；设为空字符串表示清除")
    use_sandbox: bool = False
    sandbox_base_url: str | None = Field(default=None, max_length=500)
    production_base_url: str | None = Field(default=None, max_length=500)


class WotoSettingsResponse(BaseModel):
    has_api_key: bool
    api_key_preview: str | None
    use_sandbox: bool
    sandbox_base_url: str
    production_base_url: str
    effective_base_url: str


class WotoTestRequest(BaseModel):
    environment: str = Field(default="current", description="'sandbox' | 'production' | 'current'")
    api_key: str | None = None
    base_url: str | None = None


class WotoTestResponse(BaseModel):
    success: bool
    environment: str
    base_url: str
    remain_quota: int | None = None
    error: str | None = None


def _mask_key(key: str | None) -> str | None:
    if not key:
        return None
    return f"...{key[-4:]}" if len(key) > 4 else "****"


@router.get("/woto", response_model=WotoSettingsResponse)
async def get_woto_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await get_team_woto_config(db, current_user.team_id)
    api_key = cfg["api_key"]
    return WotoSettingsResponse(
        has_api_key=bool(api_key),
        api_key_preview=_mask_key(api_key),
        use_sandbox=cfg["use_sandbox"],
        sandbox_base_url=cfg["sandbox_base_url"],
        production_base_url=cfg["production_base_url"],
        effective_base_url=cfg["effective_base_url"],
    )


@router.put("/woto", response_model=WotoSettingsResponse)
async def update_woto_settings(
    data: WotoSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, current_user.team_id)
    if not team:
        raise BadRequestException("团队不存在")

    existing: dict = team.woto_settings or {}
    updated = dict(existing)

    if data.api_key is not None:
        if data.api_key.strip():
            updated["api_key"] = data.api_key.strip()
        else:
            updated.pop("api_key", None)

    updated["use_sandbox"] = data.use_sandbox

    if data.sandbox_base_url is not None:
        if data.sandbox_base_url.strip():
            updated["sandbox_base_url"] = data.sandbox_base_url.strip()
        else:
            updated.pop("sandbox_base_url", None)

    if data.production_base_url is not None:
        if data.production_base_url.strip():
            updated["production_base_url"] = data.production_base_url.strip()
        else:
            updated.pop("production_base_url", None)

    team.woto_settings = updated
    await db.commit()

    cfg = await get_team_woto_config(db, current_user.team_id)
    api_key = cfg["api_key"]
    return WotoSettingsResponse(
        has_api_key=bool(api_key),
        api_key_preview=_mask_key(api_key),
        use_sandbox=cfg["use_sandbox"],
        sandbox_base_url=cfg["sandbox_base_url"],
        production_base_url=cfg["production_base_url"],
        effective_base_url=cfg["effective_base_url"],
    )


@router.post("/woto/test", response_model=WotoTestResponse)
async def test_woto_connection(
    data: WotoTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test Woto API connectivity for sandbox or production environment."""
    cfg = await get_team_woto_config(db, current_user.team_id)

    if data.environment == "sandbox":
        base_url = data.base_url or cfg["sandbox_base_url"] or WOTO_PRODUCTION_BASE_URL
        env_label = "sandbox"
    elif data.environment == "production":
        base_url = data.base_url or cfg["production_base_url"]
        env_label = "production"
    else:
        base_url = cfg["effective_base_url"]
        env_label = "sandbox" if cfg["use_sandbox"] else "production"

    api_key = data.api_key or cfg["api_key"]

    try:
        async with WotoClient(api_key=api_key or None, base_url=base_url) as client:
            payload = await client.query_quota()
        raw_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        remain = raw_data.get("remainQuota")
        return WotoTestResponse(
            success=True,
            environment=env_label,
            base_url=base_url,
            remain_quota=int(remain) if remain is not None else None,
        )
    except WotoConfigurationError as exc:
        return WotoTestResponse(success=False, environment=env_label, base_url=base_url, error=str(exc))
    except WotoAPIError as exc:
        return WotoTestResponse(success=False, environment=env_label, base_url=base_url, error=str(exc))
    except Exception as exc:
        return WotoTestResponse(success=False, environment=env_label, base_url=base_url, error=f"连接失败：{exc}")


# ─────────────────────────────────────────────────────────────────────────────
# AI Provider Settings
# ─────────────────────────────────────────────────────────────────────────────


class AISettingsUpdate(BaseModel):
    provider: str = Field(..., description="Provider ID")
    api_key: str | None = Field(default=None, description="留空表示不修改")
    model: str = Field(default="")
    base_url: str | None = Field(default=None)
    # Azure OpenAI extra fields
    azure_endpoint: str | None = Field(default=None)
    api_version: str | None = Field(default=None)
    # Amazon Bedrock extra fields
    aws_region: str | None = Field(default=None)
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)


class AISettingsResponse(BaseModel):
    provider: str
    model: str
    base_url: str | None
    has_api_key: bool
    api_key_preview: str | None
    catalog: list[dict]
    # Extra fields for Azure / AWS (never return secrets, only presence)
    extra: dict = {}


class AITestResponse(BaseModel):
    success: bool
    provider: str
    model: str
    ping_response: str | None = None
    error: str | None = None


def _build_ai_settings_response(cfg: dict) -> AISettingsResponse:
    """Build a safe response from the stored AI settings dict."""
    extra: dict = {}
    # Expose presence of sensitive extra fields, not values
    if cfg.get("azure_endpoint"):
        extra["azure_endpoint"] = cfg["azure_endpoint"]
    if cfg.get("api_version"):
        extra["api_version"] = cfg["api_version"]
    if cfg.get("aws_region"):
        extra["aws_region"] = cfg["aws_region"]
    if cfg.get("aws_access_key_id"):
        extra["has_aws_access_key_id"] = True
    if cfg.get("aws_secret_access_key"):
        extra["has_aws_secret_access_key"] = True
    return AISettingsResponse(
        provider=cfg.get("provider", "claude"),
        model=cfg.get("model", ""),
        base_url=cfg.get("base_url"),
        has_api_key=bool(cfg.get("api_key")),
        api_key_preview=_mask_key(cfg.get("api_key")),
        catalog=PROVIDER_CATALOG,
        extra=extra,
    )


def _merge_ai_config(data: AISettingsUpdate, existing: dict) -> dict:
    """Merge submitted settings with existing stored values. Never clears with None."""
    updated = dict(existing)
    updated["provider"] = data.provider
    updated["model"] = data.model

    def _update_secret(key: str, value: str | None) -> None:
        if value is None:
            return  # not submitted → keep existing
        v = value.strip()
        if v:
            updated[key] = v
        else:
            updated.pop(key, None)  # empty string → clear

    _update_secret("api_key", data.api_key)
    _update_secret("base_url", data.base_url)
    _update_secret("azure_endpoint", data.azure_endpoint)
    _update_secret("api_version", data.api_version)
    _update_secret("aws_region", data.aws_region)
    _update_secret("aws_access_key_id", data.aws_access_key_id)
    _update_secret("aws_secret_access_key", data.aws_secret_access_key)
    return updated


def _build_test_cfg(data: AISettingsUpdate, existing: dict) -> dict:
    """Build a full config dict for the test call, merging form values with saved values."""
    def _val(key: str, submitted: str | None) -> str:
        v = (submitted or "").strip()
        return v or existing.get(key, "")

    return {
        "provider": data.provider,
        "model": data.model,
        "api_key": _val("api_key", data.api_key),
        "base_url": _val("base_url", data.base_url) or None,
        "azure_endpoint": _val("azure_endpoint", data.azure_endpoint) or None,
        "api_version": _val("api_version", data.api_version) or "2024-02-01",
        "aws_region": _val("aws_region", data.aws_region) or "us-east-1",
        "aws_access_key_id": _val("aws_access_key_id", data.aws_access_key_id),
        "aws_secret_access_key": _val("aws_secret_access_key", data.aws_secret_access_key),
    }


@router.get("/ai", response_model=AISettingsResponse)
async def get_ai_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.config import settings as env_settings

    team = await db.get(Team, current_user.team_id)
    cfg: dict = (team.ai_settings if team else None) or {}

    # If no DB config, reflect env defaults
    if not cfg.get("provider"):
        cfg = {"provider": env_settings.ai_provider or "claude", "model": ""}

    return _build_ai_settings_response(cfg)


@router.put("/ai", response_model=AISettingsResponse)
async def update_ai_settings(
    data: AISettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, current_user.team_id)
    if not team:
        raise BadRequestException("团队不存在")

    team.ai_settings = _merge_ai_config(data, team.ai_settings or {})
    await db.commit()
    await db.refresh(team)
    return _build_ai_settings_response(team.ai_settings or {})


@router.post("/ai/test", response_model=AITestResponse)
async def test_ai_connection(
    data: AISettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a minimal ping to verify credentials and model connectivity."""
    team = await db.get(Team, current_user.team_id)
    existing_cfg: dict = (team.ai_settings if team else None) or {}
    cfg = _build_test_cfg(data, existing_cfg)

    try:
        provider = get_ai_provider(cfg)
        # Use ping() if available, otherwise fall back to a simple convert
        if hasattr(provider, "ping"):
            pong = await provider.ping()
        else:
            result = await provider.convert_template("hi", "hello world")
            pong = result.get("subject") or str(result)[:80]
        return AITestResponse(
            success=True,
            provider=data.provider,
            model=data.model,
            ping_response=pong[:200] if pong else "ok",
        )
    except Exception as exc:
        return AITestResponse(
            success=False,
            provider=data.provider,
            model=data.model,
            error=str(exc),
        )
