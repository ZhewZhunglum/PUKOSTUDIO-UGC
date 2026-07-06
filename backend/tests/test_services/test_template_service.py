from app.services.template_service import (
    build_influencer_variables,
    extract_variables,
    render_template,
)


class _StubPlatform:
    def __init__(self, platform, username, followers):
        self.platform = platform
        self.username = username
        self.followers = followers


class _StubInfluencer:
    def __init__(self, *, name=None, email=None, niche=None, country=None, platforms=None):
        self.name = name
        self.email = email
        self.niche = niche
        self.country = country
        self.platforms = platforms or []


def test_extract_variables_returns_unique_placeholders():
    variables = extract_variables("Hi {{name}}, welcome to {{brand}}. {{name}}")

    assert sorted(variables) == ["brand", "name"]


def test_render_template_replaces_known_variables():
    subject, body = render_template(
        "Hi {{first_name}}",
        "<p>{{first_name}}, welcome to {{brand}}</p>",
        {"first_name": "Sam", "brand": "UGC Outreach"},
    )

    assert subject == "Hi Sam"
    assert body == "<p>Sam, welcome to UGC Outreach</p>"


def test_build_influencer_variables_covers_documented_placeholders():
    influencer = _StubInfluencer(
        name="Jane Doe",
        email="jane@example.com",
        niche="beauty",
        country="US",
        platforms=[_StubPlatform("tiktok", "janeugc", 12000)],
    )

    variables = build_influencer_variables(influencer)

    assert variables == {
        "name": "Jane Doe",
        "first_name": "Jane",
        "email": "jane@example.com",
        "niche": "beauty",
        "country": "US",
        "platform": "tiktok",
        "username": "janeugc",
        "followers": "12000",
    }


def test_build_influencer_variables_handles_none_and_missing_fields():
    variables = build_influencer_variables(None, fallback_name="Sam Smith")

    assert variables["name"] == "Sam Smith"
    assert variables["first_name"] == "Sam"
    # No influencer / no platform → documented vars resolve to empty, never None.
    assert variables["email"] == ""
    assert variables["platform"] == ""
    assert variables["followers"] == ""


def test_render_template_resolves_influencer_variables_end_to_end():
    influencer = _StubInfluencer(
        name="Jane",
        niche="beauty",
        platforms=[_StubPlatform("tiktok", "jane", 5000)],
    )

    subject, body = render_template(
        "Hi {{first_name}}",
        "<p>{{niche}} creator on {{platform}} with {{followers}} fans</p>",
        build_influencer_variables(influencer),
    )

    assert subject == "Hi Jane"
    assert body == "<p>beauty creator on tiktok with 5000 fans</p>"
