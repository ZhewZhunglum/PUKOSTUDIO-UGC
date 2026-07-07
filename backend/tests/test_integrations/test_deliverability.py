from app.integrations.email.manager import (
    WARMUP_CAPS,
    effective_daily_limit,
    inject_unsubscribe,
    unsubscribe_headers,
    unsubscribe_url,
)
from app.services.suppression_service import normalize_email


class _StubAccount:
    def __init__(self, daily_limit: int, warmup_stage: int):
        self.daily_limit = daily_limit
        self.warmup_stage = warmup_stage


def test_effective_daily_limit_respects_warmup_ramp():
    # Fresh account: capped by stage 0 even with a huge configured limit.
    assert effective_daily_limit(_StubAccount(daily_limit=5000, warmup_stage=0)) == WARMUP_CAPS[0]
    # Mid-ramp.
    assert effective_daily_limit(_StubAccount(daily_limit=5000, warmup_stage=3)) == WARMUP_CAPS[3]
    # Fully warmed: configured limit wins.
    assert effective_daily_limit(_StubAccount(daily_limit=5000, warmup_stage=len(WARMUP_CAPS))) == 5000
    # Configured limit below the ramp cap always wins.
    assert effective_daily_limit(_StubAccount(daily_limit=30, warmup_stage=5)) == 30


def test_warmup_caps_monotonically_increase():
    assert all(a < b for a, b in zip(WARMUP_CAPS, WARMUP_CAPS[1:]))


def test_unsubscribe_headers_are_rfc8058():
    headers = unsubscribe_headers("http://localhost:8917", "abc")
    assert headers["List-Unsubscribe"] == "<http://localhost:8917/api/v1/track/unsubscribe/abc>"
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_inject_unsubscribe_appends_footer_link():
    out = inject_unsubscribe("<p>Hi</p>", "msg-1", "http://localhost:8917")
    assert unsubscribe_url("http://localhost:8917", "msg-1") in out
    assert "退订" in out


def test_inject_unsubscribe_stays_inside_body_tag():
    out = inject_unsubscribe("<html><body><p>Hi</p></body></html>", "m", "http://x")
    assert out.index("退订") < out.index("</body>")


def test_normalize_email_lowercases_and_trims():
    assert normalize_email("  Jane@Example.COM ") == "jane@example.com"
    assert normalize_email(None) == ""
    assert normalize_email("") == ""
