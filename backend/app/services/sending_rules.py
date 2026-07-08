"""Pure scheduling/AB rules for campaign sending.

Kept free of DB/Celery imports so every rule is unit-testable:
- send window: only dispatch inside the configured local-time window
- A/B subject: deterministic 50/50 split by influencer id
- follow-up: which step is due next and when
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "UTC"


def _window(schedule_config: dict | None) -> dict | None:
    if not schedule_config:
        return None
    window = schedule_config.get("send_window")
    if not isinstance(window, dict):
        return None
    start = window.get("start_hour")
    end = window.get("end_hour")
    if start is None or end is None:
        return None
    try:
        start, end = int(start), int(end)
    except (TypeError, ValueError):
        return None
    if not (0 <= start < 24 and 0 < end <= 24 and start < end):
        return None
    return {"start": start, "end": end, "tz": str(window.get("timezone") or DEFAULT_TZ)}


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def seconds_until_send_window(schedule_config: dict | None, now: datetime) -> int:
    """0 if sending is allowed right now, else seconds until the window opens.

    A campaign without a (valid) send_window can send at any time. ``now`` must
    be timezone-aware.
    """
    window = _window(schedule_config)
    if window is None:
        return 0

    local = now.astimezone(_tz(window["tz"]))
    if window["start"] <= local.hour < window["end"]:
        return 0

    opens = local.replace(hour=window["start"], minute=0, second=0, microsecond=0)
    if local.hour >= window["end"]:
        opens += timedelta(days=1)
    return max(1, int((opens - local).total_seconds()))


def choose_ab_subject(
    influencer_id: uuid.UUID | str, subject_a: str, subject_b: str | None
) -> tuple[str, str]:
    """Deterministic 50/50 subject split. Returns (subject, variant).

    Hash-based so retries/redelivery always pick the same variant for the same
    influencer (idempotent), with no coordination or storage needed.
    """
    if not subject_b or not subject_b.strip():
        return subject_a, "A"
    digest = hashlib.sha256(str(influencer_id).encode("utf-8")).digest()
    return (subject_a, "A") if digest[0] % 2 == 0 else (subject_b, "B")


def next_due_step(
    steps: list, current_step: int, last_sent_at: datetime | None, now: datetime
) -> object | None:
    """The next follow-up step that is due now, or None.

    ``steps`` are CampaignStep-shaped objects (step_order, delay_days) sorted or
    not. A step is due when its order is the smallest one greater than
    ``current_step`` and ``last_sent_at + delay_days`` has passed. Enrollments
    that never sent (last_sent_at None) are not follow-up candidates.
    """
    if last_sent_at is None:
        return None
    upcoming = sorted(
        (s for s in steps if s.step_order > current_step), key=lambda s: s.step_order
    )
    if not upcoming:
        return None
    nxt = upcoming[0]
    due_at = last_sent_at + timedelta(days=nxt.delay_days or 0)
    return nxt if now >= due_at else None
