"""Turn user input (bare handles, profile URLs, channel ids) into fetch targets.

Port of creator-finder server/profiles.mjs: resolveTarget / profileUrlFor /
tiktokHandleFromUrl / profileIdentityFromRedirect.
"""
import re
from dataclasses import dataclass
from urllib.parse import urlparse

CHANNEL_ID_RE = re.compile(r"^UC[0-9A-Za-z_-]{22}$")


@dataclass
class Target:
    platform: str
    handle: str
    profile_url: str


def _host(url: str) -> str | None:
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return re.sub(r"^www\.", "", host.lower())


def profile_url_for(platform: str, handle: str) -> str | None:
    """Build the public profile URL to fetch for a platform + handle."""
    h = str(handle).strip().lstrip("@")
    if not h:
        return None
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{h}"
    if platform == "youtube":
        return f"https://www.youtube.com/@{h}/about"
    if platform == "instagram":
        return f"https://www.instagram.com/{h}/"
    return None


def tiktok_handle_from_url(value: str) -> str | None:
    host = _host(value)
    if not host or not host.endswith("tiktok.com"):
        return None
    segments = [s for s in urlparse(value).path.split("/") if s]
    for segment in segments:
        if segment.startswith("@"):
            return segment[1:]
    return None


def profile_identity_from_redirect(target: Target, final_url: str) -> dict:
    """After following redirects, a TikTok share link reveals the real handle."""
    redirected = tiktok_handle_from_url(final_url) if target.platform == "tiktok" else None
    return {
        "handle": redirected or target.handle,
        "profile_url": final_url or target.profile_url,
        "display_name": redirected,
    }


def resolve_target(entry: str, default_platform: str) -> Target | None:
    """Turn a form entry (a username or a full profile URL) into a fetch target.

    default_platform is used when the entry is a bare handle.
    """
    value = str(entry).strip()
    if not value:
        return None

    if re.match(r"^https?://", value, re.IGNORECASE):
        host = _host(value)
        if not host:
            return None
        segments = [s for s in urlparse(value).path.split("/") if s]
        if host.endswith("tiktok.com"):
            handle = next((s[1:] for s in segments if s.startswith("@")), None)
            if handle:
                return Target("tiktok", handle, profile_url_for("tiktok", handle))
            if len(segments) >= 3 and segments[0] == "share" and segments[1] == "user":
                return Target("tiktok", segments[2], value)
            return None
        if host.endswith("youtube.com"):
            at = next((s for s in segments if s.startswith("@")), None)
            if at:
                return Target("youtube", at[1:], profile_url_for("youtube", at[1:]))
            if len(segments) >= 2 and segments[0] == "channel":
                return Target(
                    "youtube", segments[1], f"https://www.youtube.com/channel/{segments[1]}/about"
                )
            return None
        if host.endswith("instagram.com"):
            if segments:
                return Target("instagram", segments[0], profile_url_for("instagram", segments[0]))
            return None
        return None

    # A bare "UC" + 22 chars is a YouTube channel id regardless of the selected platform.
    if CHANNEL_ID_RE.match(value):
        return Target("youtube", value, f"https://www.youtube.com/channel/{value}/about")

    handle = value.lstrip("@")
    profile_url = profile_url_for(default_platform, handle)
    if not profile_url:
        return None
    return Target(default_platform, handle, profile_url)
