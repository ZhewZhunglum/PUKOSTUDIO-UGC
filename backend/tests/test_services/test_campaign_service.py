import uuid
from types import SimpleNamespace

from app.services.campaign_service import (
    MAX_STEP_ATTACHMENT_BYTES,
    _overflowing_step_orders,
)


def _step(step_order: int, attachment_ids: list) -> SimpleNamespace:
    return SimpleNamespace(step_order=step_order, attachment_ids=attachment_ids)


def test_overflowing_step_orders_flags_steps_over_the_cap():
    small_id, big_id = uuid.uuid4(), uuid.uuid4()
    size_by_id = {small_id: 1024, big_id: MAX_STEP_ATTACHMENT_BYTES + 1}

    steps = [_step(1, [small_id]), _step(2, [big_id])]

    assert _overflowing_step_orders(steps, size_by_id) == [2]


def test_overflowing_step_orders_allows_exactly_the_cap():
    # Exactly at the limit is allowed — only strictly-over is rejected.
    at_cap = uuid.uuid4()
    steps = [_step(1, [at_cap])]

    assert _overflowing_step_orders(steps, {at_cap: MAX_STEP_ATTACHMENT_BYTES}) == []


def test_overflowing_step_orders_sums_multiple_attachments_per_step():
    a, b = uuid.uuid4(), uuid.uuid4()
    half = MAX_STEP_ATTACHMENT_BYTES // 2
    size_by_id = {a: half, b: half + 1}

    steps = [_step(1, [a, b])]

    assert _overflowing_step_orders(steps, size_by_id) == [1]


def test_overflowing_step_orders_ignores_unknown_ids():
    # An id missing from size_by_id (already deleted, or belongs to another
    # team) contributes 0 bytes rather than raising — matches the lenient
    # "silently skip" behavior of attachment_payloads_for_ids.
    steps = [_step(1, [uuid.uuid4()])]

    assert _overflowing_step_orders(steps, {}) == []


def test_overflowing_step_orders_returns_empty_for_no_attachments():
    steps = [_step(1, []), _step(2, None)]

    assert _overflowing_step_orders(steps, {}) == []
