"""HTTP fetching with timeout + retries, port of creator-finder profileFetch.mjs.

Uses httpx.AsyncClient with trust_env=True so HTTPS_PROXY/HTTP_PROXY work in
deployments where the platform sites need a proxy.
"""
import asyncio
import re

import httpx

DEFAULT_USER_AGENT = "creator-finder-local/0.1 (personal research)"
FETCH_TIMEOUT_S = 8.0
ATTEMPTS = 3
RETRY_DELAY_S = 0.3

_TEXT_CONTENT_TYPE = re.compile(r"text|html|json|xml", re.IGNORECASE)


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=FETCH_TIMEOUT_S,
        trust_env=True,
        headers={"user-agent": DEFAULT_USER_AGENT},
    )


async def _fetch_once(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    try:
        response = await client.get(url)
        final_url = str(response.url) or url
        if response.status_code < 200 or response.status_code >= 300:
            return "", final_url
        content_type = response.headers.get("content-type", "")
        if content_type and not _TEXT_CONTENT_TYPE.search(content_type):
            return "", final_url
        return response.text, final_url
    except (httpx.HTTPError, ValueError):
        return "", url


async def fetch_text(client: httpx.AsyncClient, url: str) -> str:
    html, _ = await _fetch_once(client, url)
    return html


async def fetch_profile_text(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """Fetch a profile page, retrying empty responses. Returns (html, final_url)."""
    last: tuple[str, str] = ("", url)
    for attempt in range(ATTEMPTS):
        last = await _fetch_once(client, url)
        if last[0]:
            return last
        if attempt < ATTEMPTS - 1:
            await asyncio.sleep(RETRY_DELAY_S)
    return last
