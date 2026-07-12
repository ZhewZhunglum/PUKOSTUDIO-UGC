"""Unit tests for the email_finder port, mirroring the creator-finder
extension's emailDig.test.mjs + profiles.test.mjs so behavior stays aligned."""
import json

from app.integrations.email_finder.email_extract import (
    contact_urls_for,
    email_domains,
    extract_emails_from_html,
    extract_phones_from_html,
)
from app.integrations.email_finder.parsers import (
    extract_outbound_links,
    is_aggregator,
    parse_tiktok_profile_html,
    parse_youtube_about_html,
    repair_mojibake,
)
from app.integrations.email_finder.resolve import (
    Target,
    profile_identity_from_redirect,
    profile_url_for,
    resolve_target,
    tiktok_handle_from_url,
)


class TestExtractEmailsFromHtml:
    def test_pulls_emails_from_text_mailto_and_entities(self):
        html = """
          <p>Reach me at hello@brand.com</p>
          <a href="mailto:press@brand.com">press</a>
          <span>backup&#64;brand.com</span>
          <script>var x = "ignore@script.js"</script>
        """
        # page-text emails first (document order), then mailto hrefs
        assert extract_emails_from_html(html) == [
            "hello@brand.com",
            "backup@brand.com",
            "press@brand.com",
        ]

    def test_dedupes_case_insensitively_and_drops_asset_tlds(self):
        assert extract_emails_from_html("A@X.COM a@x.com sprite@sheet.png") == ["a@x.com"]

    def test_empty_or_non_string_input(self):
        assert extract_emails_from_html("") == []
        assert extract_emails_from_html(None) == []

    def test_drops_json_escape_artifacts_from_mailto(self):
        # In JSON-embedded HTML a mailto before an escaped quote captures a
        # trailing backslash; cleaning must not let that variant through.
        html = '{"html":"<a href=\\"mailto:hi@x.com\\">hi@x.com</a>"}'
        assert extract_emails_from_html(html) == ["hi@x.com"]


class TestExtractPhonesFromHtml:
    def test_pulls_wa_me_tel_links_and_international_text(self):
        html = """
          <a href="https://wa.me/8613812345678">WhatsApp</a>
          <a href="https://api.whatsapp.com/send?phone=12025550123&text=hi">chat</a>
          <a href="tel:+44 20 7946 0958">call</a>
          <p>Business: +1 (310) 555-0199</p>
        """
        assert extract_phones_from_html(html) == [
            "+8613812345678",
            "+12025550123",
            "+442079460958",
            "+13105550199",
        ]

    def test_ignores_bare_numbers_and_junk(self):
        # Follower counts / dates / short numbers must not become "phones".
        html = "<p>1,200,000 followers since 2019. Call 12345.</p>"
        assert extract_phones_from_html(html) == []
        assert extract_phones_from_html("") == []
        assert extract_phones_from_html(None) == []

    def test_dedupes_same_number_in_different_formats(self):
        html = '<a href="tel:+1-310-555-0199">call</a> +1 310 555 0199'
        assert extract_phones_from_html(html) == ["+13105550199"]


class TestContactUrlsFor:
    def test_builds_same_origin_contact_candidates(self):
        assert contact_urls_for("https://brand.com/some/page?x=1") == [
            "https://brand.com/contact",
            "https://brand.com/contact-us",
            "https://brand.com/about",
            "https://brand.com/about-us",
            "https://brand.com/info",
        ]

    def test_rejects_non_http_and_malformed_urls(self):
        assert contact_urls_for("ftp://brand.com") == []
        assert contact_urls_for("not a url") == []


class TestEmailDomains:
    def test_returns_unique_domains(self):
        assert email_domains(["a@x.com", "b@x.com", "c@y.io"]) == ["x.com", "y.io"]


class TestProfileUrlFor:
    def test_builds_public_profile_urls_per_platform(self):
        assert profile_url_for("tiktok", "@cook.sam") == "https://www.tiktok.com/@cook.sam"
        assert profile_url_for("youtube", "samcooks") == "https://www.youtube.com/@samcooks/about"
        assert profile_url_for("instagram", "sam") == "https://www.instagram.com/sam/"
        assert profile_url_for("tiktok", "") is None


class TestResolveTarget:
    def test_uses_default_platform_for_bare_handles(self):
        assert resolve_target("@cook.sam", "tiktok") == Target(
            "tiktok", "cook.sam", "https://www.tiktok.com/@cook.sam"
        )

    def test_detects_platform_and_handle_from_full_url(self):
        target = resolve_target("https://www.tiktok.com/@cook.sam?lang=en", "youtube")
        assert (target.platform, target.handle) == ("tiktok", "cook.sam")

        assert resolve_target(
            "https://www.tiktok.com/share/user/7014666138315604998", "youtube"
        ) == Target(
            "tiktok",
            "7014666138315604998",
            "https://www.tiktok.com/share/user/7014666138315604998",
        )

        target = resolve_target("https://youtube.com/@samcooks/videos", "tiktok")
        assert (target.platform, target.handle) == ("youtube", "samcooks")

        target = resolve_target("https://www.instagram.com/sam/", "tiktok")
        assert (target.platform, target.handle) == ("instagram", "sam")

    def test_bare_youtube_channel_id_routes_to_youtube(self):
        assert resolve_target("UCabcdefghijklmnopqrstuv", "tiktok") == Target(
            "youtube",
            "UCabcdefghijklmnopqrstuv",
            "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv/about",
        )

    def test_empty_or_unsupported_entries(self):
        assert resolve_target("", "tiktok") is None
        assert resolve_target("https://example.com/x", "tiktok") is None


def _tiktok_html(data: dict) -> str:
    payload = json.dumps(data)
    return (
        '<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
        f'type="application/json">{payload}</script></html>'
    )


class TestParseTikTokProfileHtml:
    def test_reads_bio_name_followers_and_bio_link(self):
        data = {
            "__DEFAULT_SCOPE__": {
                "webapp.user-detail": {
                    "userInfo": {
                        "user": {
                            "uniqueId": "cook.sam",
                            "nickname": "Sam Cooks",
                            "signature": "email sam@kitchen.com",
                            "bioLink": {"link": "https://linktr.ee/sam"},
                        },
                        "stats": {"followerCount": 88000},
                    }
                }
            }
        }
        result = parse_tiktok_profile_html(_tiktok_html(data))
        assert result.display_name == "Sam Cooks"
        assert result.bio == "email sam@kitchen.com"
        assert result.follower_count == 88000
        assert result.external_links == ["https://linktr.ee/sam"]

    def test_degrades_to_empty_on_missing_data(self):
        assert parse_tiktok_profile_html("<html>no data</html>").external_links == []

    def test_repairs_mojibake_in_names_and_bios(self):
        data = {
            "__DEFAULT_SCOPE__": {
                "webapp.user-detail": {
                    "userInfo": {
                        "user": {
                            "uniqueId": "sierra",
                            "nickname": "SIERRA â¦ SHANE",
                            "signature": "hello â¨",
                            "bioLink": {},
                        },
                        "stats": {"followerCount": 14700},
                    }
                }
            }
        }
        result = parse_tiktok_profile_html(_tiktok_html(data))
        assert result.display_name == "SIERRA ✦ SHANE"
        assert result.bio == "hello ✨"


class TestTikTokUrlHelpers:
    def test_reads_handle_from_redirected_urls(self):
        assert tiktok_handle_from_url("https://www.tiktok.com/@diana.s_8?lang=en") == "diana.s_8"
        assert tiktok_handle_from_url("https://www.tiktok.com/share/user/6952585448968897541") is None

    def test_uses_redirected_handle_when_profile_body_unavailable(self):
        target = Target(
            "tiktok",
            "6952585448968897541",
            "https://www.tiktok.com/share/user/6952585448968897541",
        )
        assert profile_identity_from_redirect(target, "https://www.tiktok.com/@diana.s_8") == {
            "handle": "diana.s_8",
            "profile_url": "https://www.tiktok.com/@diana.s_8",
            "display_name": "diana.s_8",
        }

    def test_repairs_utf8_as_latin1_mojibake(self):
        assert repair_mojibake("SIERRA â¦ SHANE") == "SIERRA ✦ SHANE"
        assert repair_mojibake("Sam Cooks") == "Sam Cooks"


class TestParseYouTubeAboutHtml:
    def test_reads_name_description_and_unwraps_redirect_links(self):
        html = """
          <meta property="og:title" content="Sam Cooks">
          <meta name="description" content="Recipes. Business: sam@kitchen.com">
          <a href="https://www.youtube.com/redirect?event=channel&q=https%3A%2F%2Fkitchen.com">site</a>
        """
        result = parse_youtube_about_html(html)
        assert result.display_name == "Sam Cooks"
        assert "sam@kitchen.com" in result.bio
        assert result.external_links == ["https://kitchen.com"]

    def test_unwraps_json_escaped_redirect_links(self):
        # Modern YouTube pages embed redirect links inside JSON, where "&" is
        # escaped as the six characters \u0026.
        html = (
            '{"url":"https://www.youtube.com/redirect?event=channel_header'
            '\\u0026redir_token=abc\\u0026q=https%3A%2F%2Fkitchen.com"}'
        )
        assert parse_youtube_about_html(html).external_links == ["https://kitchen.com"]


class TestAggregatorHelpers:
    def test_recognizes_link_aggregators(self):
        assert is_aggregator("https://linktr.ee/sam") is True
        assert is_aggregator("https://kitchen.com") is False

    def test_extracts_off_host_outbound_links(self):
        html = """
          <a href="https://linktr.ee/internal">self</a>
          <a href="https://kitchen.com/">site</a>
          <a href="https://shop.kitchen.com/deals">shop</a>
        """
        assert extract_outbound_links(html, "https://linktr.ee/sam") == [
            "https://kitchen.com/",
            "https://shop.kitchen.com/deals",
        ]
