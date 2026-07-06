import pytest
from fastapi import HTTPException

from app.api.v1.webhooks.security import verify_webhook_secret
from app.config import settings


class _FakeRequest:
    def __init__(self, query=None, headers=None):
        self.query_params = query or {}
        # Real Request headers are case-insensitive; the dependency looks up the
        # lowercase name, so normalize here.
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}


async def test_accepts_matching_token_in_query(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cret")
    # Should not raise.
    await verify_webhook_secret(_FakeRequest(query={"token": "s3cret"}))


async def test_accepts_matching_token_in_header(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cret")
    await verify_webhook_secret(_FakeRequest(headers={"X-Webhook-Token": "s3cret"}))


async def test_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cret")
    with pytest.raises(HTTPException) as exc:
        await verify_webhook_secret(_FakeRequest(query={"token": "nope"}))
    assert exc.value.status_code == 401


async def test_rejects_missing_token(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cret")
    with pytest.raises(HTTPException) as exc:
        await verify_webhook_secret(_FakeRequest())
    assert exc.value.status_code == 401


async def test_unset_secret_allows_in_development(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "app_env", "development")
    await verify_webhook_secret(_FakeRequest())


async def test_unset_secret_refused_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(HTTPException) as exc:
        await verify_webhook_secret(_FakeRequest())
    assert exc.value.status_code == 401
