"""Tests for the SES/SNS webhook subscription-confirmation flow."""
import httpx
import pytest
from fastapi import HTTPException

from app.api.v1.webhooks import ses


class _FakeRequest:
    def __init__(self, body: dict):
        self._body = body

    async def json(self) -> dict:
        return self._body


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient and records GET calls."""

    calls: list[str] = []
    response: _FakeResponse = _FakeResponse()
    error: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url: str) -> _FakeResponse:
        type(self).calls.append(url)
        if type(self).error is not None:
            raise type(self).error
        return type(self).response


@pytest.fixture
def fake_http(monkeypatch):
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.response = _FakeResponse()
    _FakeAsyncClient.error = None
    monkeypatch.setattr(ses.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


def _confirmation_body(
    subscribe_url: str = "https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription&Token=abc",
    signing_cert_url: str = "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-cert.pem",
) -> dict:
    return {
        "Type": "SubscriptionConfirmation",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-events",
        "SubscribeURL": subscribe_url,
        "SigningCertURL": signing_cert_url,
    }


async def test_confirmation_gets_subscribe_url(fake_http):
    body = _confirmation_body()

    result = await ses.ses_webhook(_FakeRequest(body), db=None)

    assert result == {"status": "ok"}
    assert fake_http.calls == [body["SubscribeURL"]]


async def test_rejects_untrusted_signing_cert_domain(fake_http):
    body = _confirmation_body(
        signing_cert_url="https://sns.us-east-1.amazonaws.com.evil.example/cert.pem"
    )

    with pytest.raises(HTTPException) as exc:
        await ses.ses_webhook(_FakeRequest(body), db=None)

    assert exc.value.status_code == 400
    assert fake_http.calls == []


async def test_rejects_non_https_subscribe_url(fake_http):
    body = _confirmation_body(
        subscribe_url="http://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription"
    )

    with pytest.raises(HTTPException) as exc:
        await ses.ses_webhook(_FakeRequest(body), db=None)

    assert exc.value.status_code == 400
    assert fake_http.calls == []


async def test_confirmation_http_error_raises_for_sns_retry(fake_http):
    fake_http.error = httpx.ConnectTimeout("timed out")

    with pytest.raises(HTTPException) as exc:
        await ses.ses_webhook(_FakeRequest(_confirmation_body()), db=None)

    assert exc.value.status_code == 400


async def test_confirmation_rejected_status_raises(fake_http):
    fake_http.response = _FakeResponse(status_code=403)

    with pytest.raises(HTTPException) as exc:
        await ses.ses_webhook(_FakeRequest(_confirmation_body()), db=None)

    assert exc.value.status_code == 400


async def test_unsubscribe_confirmation_logs_only(fake_http):
    body = {
        "Type": "UnsubscribeConfirmation",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-events",
        "SubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=ConfirmSubscription",
    }

    result = await ses.ses_webhook(_FakeRequest(body), db=None)

    assert result == {"status": "ok"}
    assert fake_http.calls == []
