"""Shared-secret authentication for provider webhook endpoints.

SES (via SNS), SendGrid, and the inbound-email parser all POST to public URLs.
Without a check, anyone who can reach these endpoints can forge delivery/open/
bounce events or inject fake inbound replies. Because we control the callback
URL registered with each provider, a shared secret carried in the URL query
(``?token=<secret>``) or the ``X-Webhook-Token`` header is a simple, dependency-
free way to reject forged requests.
"""
import hmac
import logging

from fastapi import Request

from app.config import settings
from app.core.exceptions import UnauthorizedException

logger = logging.getLogger(__name__)

_warned_missing_secret = False


async def verify_webhook_secret(request: Request) -> None:
    """FastAPI dependency: reject webhook requests without the shared secret.

    - If ``WEBHOOK_SECRET`` is unset: allow, but warn once. In a non-development
      environment an unset secret is refused outright, since it leaves the
      endpoints open to forgery.
    - Otherwise the request must present the matching secret via the ``token``
      query parameter or the ``X-Webhook-Token`` header (constant-time compare).
    """
    global _warned_missing_secret

    expected = settings.webhook_secret
    if not expected:
        if settings.app_env != "development":
            raise UnauthorizedException(
                "Webhook secret is not configured; refusing to accept "
                "unauthenticated webhooks in a non-development environment."
            )
        if not _warned_missing_secret:
            logger.warning(
                "WEBHOOK_SECRET is unset; provider webhooks are unauthenticated. "
                "Set WEBHOOK_SECRET and append ?token=<secret> to the callback URL."
            )
            _warned_missing_secret = True
        return

    provided = request.query_params.get("token") or request.headers.get("x-webhook-token")
    if not provided or not hmac.compare_digest(provided, expected):
        raise UnauthorizedException("Invalid or missing webhook token")
