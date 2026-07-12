"""Server-side public profile page parsers, port of creator-finder profiles.mjs.

TikTok/YouTube expose bio + links publicly; Instagram gates most of it, so IG
is best-effort (og: tags only).
"""
import json
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse


@dataclass
class ProfileInfo:
    display_name: str | None = None
    bio: str | None = None
    follower_count: int | None = None
    external_links: list[str] = field(default_factory=list)


def _decode_entities(text: str) -> str:
    text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"&quot;", '"', text, flags=re.IGNORECASE)
    text = re.sub(r"&#0?39;", "'", text)
    text = re.sub(r"&#x27;", "'", text, flags=re.IGNORECASE)
    text = re.sub(r"&lt;", "<", text, flags=re.IGNORECASE)
    text = re.sub(r"&gt;", ">", text, flags=re.IGNORECASE)
    return text


def _meta_content(html: str, attr: str, value: str) -> str | None:
    pattern = rf'<meta[^>]*{attr}=["\']{value}["\'][^>]*content=["\']([^"\']*)["\']'
    alt = rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*{attr}=["\']{value}["\']'
    m = re.search(pattern, html, re.IGNORECASE) or re.search(alt, html, re.IGNORECASE)
    return _decode_entities(m.group(1)) if m else None


def _unique_http(urls: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if isinstance(u, str) and re.match(r"^https?://", u, re.IGNORECASE) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def repair_mojibake(value):
    """UTF-8 bytes mis-decoded as latin-1 show up as Ã/Â/â/ð runs; undo that."""
    if not isinstance(value, str) or not re.search(r"[ÃÂâð]", value):
        return value
    try:
        repaired = value.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return value if "�" in repaired else repaired


def parse_tiktok_profile_html(html: str) -> ProfileInfo:
    m = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">([\s\S]*?)</script>',
        html,
    )
    if not m:
        return ProfileInfo()
    try:
        data = json.loads(m.group(1))
        scope = data.get("__DEFAULT_SCOPE__") or {}
        info = (scope.get("webapp.user-detail") or {}).get("userInfo") or {}
        user = info.get("user") or {}
        stats = info.get("stats") or {}
        link = (user.get("bioLink") or {}).get("link")
        follower_count = stats.get("followerCount")
        return ProfileInfo(
            display_name=repair_mojibake(user.get("nickname")),
            bio=repair_mojibake(user.get("signature")),
            follower_count=follower_count if isinstance(follower_count, int) else None,
            external_links=_unique_http([link]),
        )
    except (ValueError, TypeError, AttributeError):
        return ProfileInfo()


def parse_youtube_about_html(html: str) -> ProfileInfo:
    display_name = _meta_content(html, "property", "og:title") or _meta_content(
        html, "itemprop", "name"
    )
    bio = _meta_content(html, "name", "description") or _meta_content(
        html, "property", "og:description"
    )
    # Channel external links render as youtube.com/redirect?...&q=<encoded target>.
    # Modern pages embed these inside JSON where "&" is escaped as "\\u0026" —
    # normalize before scanning or every link is missed.
    scannable = html.replace("\\u0026", "&")
    redirects = []
    for m in re.finditer(r"youtube\.com/redirect\?[^\"']*?[?&]q=([^\"'&\\]+)", scannable, re.IGNORECASE):
        redirects.append(unquote(m.group(1)))
    return ProfileInfo(display_name=display_name, bio=bio, external_links=_unique_http(redirects))


def parse_instagram_html(html: str) -> ProfileInfo:
    # Instagram serves a login wall to logged-out server requests; og:description
    # is the most that is reliably public. Often just counts + a bio snippet.
    return ProfileInfo(
        display_name=_meta_content(html, "property", "og:title"),
        bio=_meta_content(html, "property", "og:description"),
    )


def parse_profile_html(platform: str, html: str) -> ProfileInfo:
    if platform == "tiktok":
        return parse_tiktok_profile_html(html)
    if platform == "youtube":
        return parse_youtube_about_html(html)
    if platform == "instagram":
        return parse_instagram_html(html)
    return ProfileInfo()


AGGREGATOR_HOSTS = ["linktr.ee", "beacons.ai", "linkin.bio", "lnk.bio", "linktree.com", "tap.bio", "solo.to"]


def _hostname(url: str) -> str | None:
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return re.sub(r"^www\.", "", host.lower())


def is_aggregator(url: str) -> bool:
    host = _hostname(url)
    if not host:
        return False
    return any(host == h or host.endswith(f".{h}") for h in AGGREGATOR_HOSTS)


def extract_outbound_links(html: str, current_url: str) -> list[str]:
    """Outbound (off-host) links on a page, used to crawl one level past aggregators."""
    current_host = _hostname(current_url)
    if not current_host:
        return []
    hrefs = [m.group(1) for m in re.finditer(r"href=[\"'](https?://[^\"']+)[\"']", html, re.IGNORECASE)]
    out = []
    for href in _unique_http(hrefs):
        host = _hostname(href)
        if host and host != current_host and host not in AGGREGATOR_HOSTS:
            out.append(href)
    return out
