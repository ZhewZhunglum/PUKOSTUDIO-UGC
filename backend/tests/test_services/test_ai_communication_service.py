import uuid

from app.models.ai import AIRiskLevel
from app.models.conversation import AIIntent
from app.services.ai_communication_service import (
    _normalize_risk,
    _safe_intent,
    empty_playbook_response,
)


def test_safe_intent_falls_back_to_unknown():
    assert _safe_intent("not-a-real-intent") == AIIntent.unknown


def test_normalize_risk_respects_provider_value():
    risk = _normalize_risk(AIIntent.interested, 0.95, "high")

    assert risk == AIRiskLevel.high


def test_normalize_risk_marks_negotiation_high_risk():
    risk = _normalize_risk(AIIntent.negotiation, 0.99)

    assert risk == AIRiskLevel.high


def test_empty_playbook_response_is_disabled():
    campaign_id = uuid.uuid4()

    response = empty_playbook_response(campaign_id)

    assert response["campaign_id"] == campaign_id
    assert response["id"] is None
    assert response["enabled"] is False
