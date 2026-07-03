from types import SimpleNamespace

from app.services.sop_service import get_sop_playbook, score_influencer


def make_influencer(
    *,
    email: str | None = "creator@example.com",
    followers: int | None = 120_000,
    engagement_rate: float | None = 5.4,
    niche: str | None = "beauty",
    country: str | None = "US",
):
    platform = SimpleNamespace(
        platform=SimpleNamespace(value="tiktok"),
        followers=followers,
        engagement_rate=engagement_rate,
        avg_views=None,
    )
    return SimpleNamespace(
        id=None,
        email=email,
        niche=niche,
        country=country,
        platforms=[platform],
    )


def test_get_sop_playbook_contains_core_modules():
    playbook = get_sop_playbook()

    module_ids = {module["id"] for module in playbook["modules"]}
    assert "screening" in module_ids
    assert "outreach" in module_ids
    assert "content_review" in module_ids


def test_score_influencer_ready_when_core_sop_data_is_present():
    score = score_influencer(make_influencer())

    assert score["tier"] == "A"
    assert score["recommendation"] == "ready_for_outreach"
    assert score["readiness_score"] >= 75


def test_score_influencer_flags_low_engagement():
    score = score_influencer(make_influencer(engagement_rate=2.2))

    assert score["recommendation"] != "ready_for_outreach"
    assert any("Engagement rate <3%" in flag for flag in score["flags"])
