from types import SimpleNamespace
from urllib.parse import unquote

from app.integrations.email.base import build_mime_root
from app.integrations.email.manager import (
    finalize_html_for_send,
    inject_tracking,
    rewrite_links_for_tracking,
    select_best_account,
    unsubscribe_url,
)


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


def test_inject_tracking_honors_track_path():
    result = inject_tracking("<body></body>", "1234", "http://x", track_path="client-track")

    assert "/api/v1/client-track/open/1234.png" in result


def test_rewrite_links_for_tracking_wraps_content_links():
    html = '<body><a href="https://example.com/offer">shop</a></body>'

    result = rewrite_links_for_tracking(html, "1234", "http://localhost:8000")

    assert 'href="http://localhost:8000/api/v1/track/click/1234?url=' in result
    assert "https%3A%2F%2Fexample.com%2Foffer" in result
    # The original destination must survive round-trip through the redirect,
    # not just look plausible in the raw string.
    assert unquote(result.split("url=")[1].split('"')[0]) == "https://example.com/offer"


def test_rewrite_links_for_tracking_skips_non_http_links():
    html = (
        '<body><a href="mailto:a@b.com">mail</a> '
        '<a href="tel:+10000000000">call</a> '
        '<a href="#top">top</a></body>'
    )

    result = rewrite_links_for_tracking(html, "1234", "http://x")

    assert result == html  # nothing rewritten — output is untouched


def test_rewrite_links_for_tracking_honors_track_path():
    html = '<body><a href="https://example.com">go</a></body>'

    result = rewrite_links_for_tracking(html, "1234", "http://x", track_path="client-track")

    assert "/api/v1/client-track/click/1234?url=" in result


def test_rewrite_links_for_tracking_is_a_noop_without_links():
    html = "<body><p>No links here.</p></body>"

    assert rewrite_links_for_tracking(html, "1234", "http://x") == html


def test_unsubscribe_url_default_track_path_unchanged():
    assert unsubscribe_url("http://x", "m1") == "http://x/api/v1/track/unsubscribe/m1"


def test_unsubscribe_url_custom_track_path():
    assert (
        unsubscribe_url("http://x", "m1", track_path="client-track")
        == "http://x/api/v1/client-track/unsubscribe/m1"
    )


def test_finalize_inlines_style_block():
    html = '<html><head><style>.foo{color:red}</style></head><body><p class="foo">hi</p></body></html>'

    result = finalize_html_for_send(html)

    assert "<style>" not in result
    assert 'style="color:red"' in result


def test_finalize_is_idempotent():
    html = '<html><head><style>.foo{color:red}</style></head><body><p class="foo">hi</p></body></html>'

    once = finalize_html_for_send(html)
    twice = finalize_html_for_send(once)

    assert once == twice


def test_finalize_preserves_existing_inline_styles():
    html = '<p style="color:blue">hi</p>'

    result = finalize_html_for_send(html)

    assert 'color:blue' in result


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
