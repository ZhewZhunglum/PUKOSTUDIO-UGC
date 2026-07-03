from types import SimpleNamespace

from app.integrations.email.base import build_mime_root
from app.integrations.email.manager import inject_tracking, select_best_account


def make_account(
    *,
    is_active: bool = True,
    health_status: str = "healthy",
    sent_today: int = 0,
    daily_limit: int = 50,
    email_address: str = "team@example.com",
):
    return SimpleNamespace(
        is_active=is_active,
        health_status=SimpleNamespace(value=health_status),
        sent_today=sent_today,
        daily_limit=daily_limit,
        email_address=email_address,
    )


def test_select_best_account_prefers_highest_remaining_capacity():
    lower_capacity = make_account(sent_today=40, daily_limit=50, email_address="a@example.com")
    higher_capacity = make_account(sent_today=10, daily_limit=50, email_address="b@example.com")

    selected = select_best_account([lower_capacity, higher_capacity])

    assert selected.email_address == "b@example.com"


def test_select_best_account_ignores_unhealthy_accounts():
    degraded = make_account(health_status="degraded", email_address="bad@example.com")
    healthy = make_account(health_status="healthy", email_address="good@example.com")

    selected = select_best_account([degraded, healthy])

    assert selected.email_address == "good@example.com"


def test_inject_tracking_appends_pixel():
    html = "<html><body><p>Hello</p></body></html>"

    result = inject_tracking(html, "1234", "http://localhost:8000")

    assert "/api/v1/track/open/1234.png" in result
    assert result.endswith("</body></html>")


def test_build_mime_root_without_attachments_is_alternative():
    msg = build_mime_root("<p>hi</p>", "hi", None)

    assert msg.get_content_type() == "multipart/alternative"
    subtypes = [part.get_content_type() for part in msg.get_payload()]
    assert subtypes == ["text/plain", "text/html"]


def test_build_mime_root_with_attachments_is_mixed():
    attachments = [
        {"filename": "quote.pdf", "content_bytes": b"%PDF-1.4 test", "content_type": "application/pdf"}
    ]

    msg = build_mime_root("<p>hi</p>", "hi", attachments)

    assert msg.get_content_type() == "multipart/mixed"
    parts = msg.get_payload()
    assert parts[0].get_content_type() == "multipart/alternative"
    assert parts[1].get_content_type() == "application/pdf"
    assert parts[1].get_filename() == "quote.pdf"
    assert parts[1]["Content-Disposition"].startswith("attachment")
    # The full tree must serialize for the SES raw-email path.
    serialized = msg.as_string()
    assert "application/pdf" in serialized and "attachment" in serialized
