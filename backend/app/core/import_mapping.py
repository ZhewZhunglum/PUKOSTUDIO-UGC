"""Smart header/value normalization for influencer spreadsheet imports.

The import endpoint requires the canonical lower-case English headers from the
README template (name, email, platform, ...). Files exported from other tools
(e.g. the creator-finder extension: platform, username, displayName,
profileUrl, emails, followerCount, ...) or files with Chinese headers used to
be skipped row-by-row with "Missing name". This module maps common header
variants onto the canonical fields and cleans cell values so those files
import without manual renaming.

Pure stdlib on purpose so it stays unit-testable without app dependencies.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# The fixed import template, also used for the downloadable sample file.
CANONICAL_HEADERS = [
    "name", "email", "niche", "country", "platform",
    "username", "followers", "engagement_rate", "avg_views", "profile_url",
]

# Alias lookup uses "squashed" header keys: lower-cased with spaces, hyphens
# and underscores removed, so "Display Name", "display_name" and "displayName"
# all resolve the same way.
_ALIASES: dict[str, tuple[str, ...]] = {
    "name": (
        "name", "displayname", "nickname", "creatorname", "fullname",
        "昵称", "姓名", "名称", "达人", "达人名称", "达人昵称", "红人", "博主",
        "红人名", "红人名称", "红人昵称", "达人名",
    ),
    "email": ("email", "emails", "mail", "邮箱", "电子邮箱", "邮件"),
    "username": (
        "username", "handle", "account", "uid", "userid", "screenname",
        "用户名", "账号", "账户",
    ),
    "platform": ("platform", "平台", "渠道"),
    "followers": (
        "followers", "followercount", "fans", "fanscount", "subscribers",
        "粉丝", "粉丝数", "粉丝量",
    ),
    "engagement_rate": ("engagementrate", "互动率", "互动率%"),
    "avg_views": (
        "avgviews", "averageviews", "平均播放", "平均播放量", "平均观看",
        "近60天平均观看量", "近30天平均观看量", "平均观看量",
    ),
    "profile_url": (
        "profileurl", "url", "link", "profilelink", "homepage",
        "主页", "链接", "主页链接", "红人主页链接", "达人主页链接",
    ),
    # Channel ids (e.g. YouTube UC...) are a last-resort username: a handle
    # derived from the profile URL is always preferred.
    "_channel_id": ("channelid", "channel", "频道id", "频道"),
    "niche": ("niche", "category", "vertical", "领域", "类目", "垂类", "分类"),
    "country": ("country", "region", "inferredregion", "国家", "地区"),
}

_EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,24}$", re.IGNORECASE)

_PLATFORM_VALUES = {
    "tiktok": "tiktok", "tt": "tiktok", "抖音": "tiktok",
    "instagram": "instagram", "ig": "instagram", "insta": "instagram", "ins": "instagram",
    "youtube": "youtube", "yt": "youtube", "ytb": "youtube", "油管": "youtube",
}

# Common Chinese country names → ISO-3166 alpha-2 (the DB column is 2 chars).
_COUNTRY_NAMES = {
    "美国": "US", "英国": "GB", "加拿大": "CA", "澳大利亚": "AU", "德国": "DE",
    "法国": "FR", "日本": "JP", "韩国": "KR", "新加坡": "SG", "马来西亚": "MY",
    "印度尼西亚": "ID", "泰国": "TH", "越南": "VN", "菲律宾": "PH", "墨西哥": "MX",
    "巴西": "BR", "中国": "CN", "中国香港": "HK", "中国台湾": "TW", "沙特阿拉伯": "SA",
    "阿联酋": "AE", "西班牙": "ES", "意大利": "IT", "荷兰": "NL", "印度": "IN",
}


def _squash(header: str) -> str:
    return re.sub(r"[\s_\-]+", "", header.strip().lower())


def _pick(squashed_row: dict[str, str], canonical: str) -> str:
    for alias in _ALIASES[canonical]:
        value = squashed_row.get(alias, "")
        if value:
            return value
    return ""


def _clean_email(value: str) -> str:
    # Multi-email cells ("a@x.com; b@y.com") keep the first valid address.
    for candidate in re.split(r"[;,，；\s]+", value):
        candidate = candidate.strip().strip("<>\"'").lower()
        if candidate and _EMAIL_RE.match(candidate):
            return candidate
    return ""


def _clean_count(value: str) -> str:
    """Normalize follower-style counts to a plain digit string ("" if unusable).

    Accepts "12,000", "12.5k", "1.2M", "3 400", "1.2万", "0.5亿". The import
    service only trusts str.isdigit(), so anything else must be resolved here
    or dropped.
    """
    text = value.strip().lower().replace(",", "").replace(" ", "")
    m = re.match(r"^(\d+(?:\.\d+)?)([km万w亿]?)$", text)
    if not m:
        return ""
    number = float(m.group(1))
    unit = m.group(2)
    if unit == "k":
        number *= 1_000
    elif unit in ("万", "w"):
        number *= 10_000
    elif unit == "m":
        number *= 1_000_000
    elif unit == "亿":
        number *= 100_000_000
    return str(int(number))


def _clean_rate(value: str) -> str:
    text = value.strip().rstrip("%").strip()
    try:
        float(text)
    except ValueError:
        return ""
    return text


def _clean_country(value: str) -> str:
    text = value.strip()
    if text in _COUNTRY_NAMES:
        return _COUNTRY_NAMES[text]
    text = text.upper()
    return text if re.match(r"^[A-Z]{2}$", text) else ""


def _identity_from_profile_url(url: str) -> tuple[str, str]:
    """Derive (platform, username) from a profile URL; ("", "") if unknown."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
    except ValueError:
        return "", ""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    segments = [s for s in parsed.path.split("/") if s]
    if host.endswith("tiktok.com"):
        at = next((s for s in segments if s.startswith("@")), "")
        return ("tiktok", at[1:]) if at else ("", "")
    if host.endswith("instagram.com"):
        return ("instagram", segments[0]) if segments else ("", "")
    if host.endswith("youtube.com"):
        at = next((s for s in segments if s.startswith("@")), "")
        if at:
            return "youtube", at[1:]
        if len(segments) >= 2 and segments[0] in ("channel", "c", "user"):
            return "youtube", segments[1]
        return "", ""
    return "", ""


def normalize_import_row(row: dict[str, str]) -> dict[str, str]:
    """Map one parsed spreadsheet row onto the canonical import fields.

    Input keys are the trimmed lower-cased headers from parse_tabular; values
    are trimmed strings. Returns a dict containing only canonical keys.
    """
    squashed = {_squash(k): v.strip() for k, v in row.items() if k}

    platform = _PLATFORM_VALUES.get(_pick(squashed, "platform").strip().lower(), "")
    username = _pick(squashed, "username").lstrip("@").strip()
    profile_url = _pick(squashed, "profile_url")

    if profile_url and (not platform or not username):
        derived_platform, derived_username = _identity_from_profile_url(profile_url)
        platform = platform or derived_platform
        username = username or derived_username

    # Last resort: a channel id (e.g. YouTube "UC...") still identifies the
    # account when neither a username column nor a parseable URL exists.
    username = username or _pick(squashed, "_channel_id").strip()

    # Rows without an explicit name fall back to the handle so exports that
    # only carry usernames (e.g. creator-finder) still import.
    name = _pick(squashed, "name") or username

    return {
        "name": name,
        "email": _clean_email(_pick(squashed, "email")),
        "niche": _pick(squashed, "niche"),
        "country": _clean_country(_pick(squashed, "country")),
        "platform": platform,
        "username": username,
        "followers": _clean_count(_pick(squashed, "followers")),
        "engagement_rate": _clean_rate(_pick(squashed, "engagement_rate")),
        "avg_views": _clean_count(_pick(squashed, "avg_views")),
        "profile_url": profile_url,
    }
