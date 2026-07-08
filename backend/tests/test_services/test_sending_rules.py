import uuid
from datetime import datetime, timedelta, timezone

from app.services.sending_rules import (
    choose_ab_subject,
    next_due_step,
    seconds_until_send_window,
)


class _Step:
    def __init__(self, step_order, delay_days):
        self.step_order = step_order
        self.delay_days = delay_days


def test_no_window_always_allows():
    now = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    assert seconds_until_send_window(None, now) == 0
    assert seconds_until_send_window({}, now) == 0
    assert seconds_until_send_window({"send_window": {"start_hour": None}}, now) == 0


def test_inside_window_allows():
    cfg = {"send_window": {"start_hour": 9, "end_hour": 17, "timezone": "UTC"}}
    now = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert seconds_until_send_window(cfg, now) == 0


def test_before_window_waits_until_open_same_day():
    cfg = {"send_window": {"start_hour": 9, "end_hour": 17, "timezone": "UTC"}}
    now = datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc)  # 2h before 9:00
    assert seconds_until_send_window(cfg, now) == 2 * 3600


def test_after_window_waits_until_next_day():
    cfg = {"send_window": {"start_hour": 9, "end_hour": 17, "timezone": "UTC"}}
    now = datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)  # after 17:00 → next 9:00 = +13h
    assert seconds_until_send_window(cfg, now) == 13 * 3600


def test_window_respects_timezone():
    # 9-17 Shanghai (UTC+8); at 02:00 UTC it's 10:00 Shanghai → inside window.
    cfg = {"send_window": {"start_hour": 9, "end_hour": 17, "timezone": "Asia/Shanghai"}}
    now = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    assert seconds_until_send_window(cfg, now) == 0


def test_invalid_timezone_falls_back_to_utc():
    cfg = {"send_window": {"start_hour": 9, "end_hour": 17, "timezone": "Mars/Phobos"}}
    now = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert seconds_until_send_window(cfg, now) == 0


def test_ab_subject_without_variant_returns_a():
    subject, variant = choose_ab_subject(uuid.uuid4(), "Hello A", None)
    assert (subject, variant) == ("Hello A", "A")
    subject, variant = choose_ab_subject(uuid.uuid4(), "Hello A", "   ")
    assert variant == "A"


def test_ab_subject_is_deterministic_and_splits():
    ids = [uuid.uuid4() for _ in range(200)]
    picks = {i: choose_ab_subject(i, "A", "B") for i in ids}
    # Deterministic: same id → same result.
    for i in ids:
        assert choose_ab_subject(i, "A", "B") == picks[i]
    variants = [v for _, v in picks.values()]
    # Roughly balanced (not degenerate).
    assert 60 < variants.count("A") < 140
    assert variants.count("A") + variants.count("B") == 200


def test_next_due_step_none_when_never_sent():
    steps = [_Step(1, 0), _Step(2, 3)]
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert next_due_step(steps, current_step=0, last_sent_at=None, now=now) is None


def test_next_due_step_waits_for_delay():
    steps = [_Step(1, 0), _Step(2, 3)]
    last = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # 2 days later: step 2 (delay 3d) not yet due.
    assert next_due_step(steps, 1, last, last + timedelta(days=2)) is None
    # 3 days later: due.
    due = next_due_step(steps, 1, last, last + timedelta(days=3))
    assert due is not None and due.step_order == 2


def test_next_due_step_none_after_last_step():
    steps = [_Step(1, 0), _Step(2, 3)]
    last = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert next_due_step(steps, 2, last, last + timedelta(days=30)) is None
