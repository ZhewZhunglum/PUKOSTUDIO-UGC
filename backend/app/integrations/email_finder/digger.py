"""Orchestration: profile → bio/link emails → MX-validated results.

Port of creator-finder index.mjs digUrl / digCreator / handleBatch.
"""
import asyncio
from dataclasses import dataclass, field

import httpx

from app.integrations.email_finder.email_extract import (
    contact_urls_for,
    extract_emails_from_html,
    extract_phones_from_html,
)
from app.integrations.email_finder.fetcher import fetch_profile_text, fetch_text, make_client
from app.integrations.email_finder.mx import mx_validate
from app.integrations.email_finder.parsers import (
    extract_outbound_links,
    is_aggregator,
    parse_profile_html,
)
from app.integrations.email_finder.resolve import Target, profile_identity_from_redirect

CONCURRENCY = 5
MAX_AGGREGATOR_LINKS = 6
MAX_BATCH = 1000
# YouTube about pages now embed every video-description link too; digging all
# of them would take minutes per creator. The channel's own links come first.
MAX_PROFILE_LINKS = 8
# One creator's external links are dug concurrently (like the original
# extension's mapPool) — serial digging made a link-heavy creator take minutes.
LINK_CONCURRENCY = 5


@dataclass
class DigResult:
    platform: str
    handle: str
    profile_url: str
    display_name: str | None = None
    follower_count: int | None = None
    bio: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    status: str = "no-email"  # found | no-email | unreachable | unresolved

    def as_dict(self) -> dict:
        return {
            "platform": self.platform,
            "handle": self.handle,
            "profile_url": self.profile_url,
            "display_name": self.display_name,
            "follower_count": self.follower_count,
            "bio": self.bio,
            "emails": self.emails,
            "phones": self.phones,
            "links": self.links,
            "status": self.status,
        }


async def dig_url(client: httpx.AsyncClient, url: str) -> tuple[list[str], list[str]]:
    """Emails and phones on a page; falls through aggregator outbound links,
    then contact pages. Returns (mx_validated_emails, phones)."""
    html = await fetch_text(client, url)
    emails = extract_emails_from_html(html)
    phones = extract_phones_from_html(html)

    # Link aggregator (Linktree/Beacons): the real contact is usually on the
    # sites it points to, so crawl one level of its outbound links.
    if not emails and is_aggregator(url):
        for outbound in extract_outbound_links(html, url)[:MAX_AGGREGATOR_LINKS]:
            outbound_html = await fetch_text(client, outbound)
            found = extract_emails_from_html(outbound_html)
            phones.extend(extract_phones_from_html(outbound_html))
            if found:
                emails = found
                break

    if not emails:
        # Still nothing — try one level of contact/about pages.
        for contact_url in contact_urls_for(url):
            contact_html = await fetch_text(client, contact_url)
            found = extract_emails_from_html(contact_html)
            phones.extend(extract_phones_from_html(contact_html))
            if found:
                emails = found
                break

    return await mx_validate(emails), phones


async def dig_creator(client: httpx.AsyncClient, target: Target) -> DigResult:
    html, final_url = await fetch_profile_text(client, target.profile_url)
    identity = profile_identity_from_redirect(target, final_url)
    if not html:
        return DigResult(
            platform=target.platform,
            handle=identity["handle"],
            profile_url=identity["profile_url"],
            status="unreachable",
        )

    profile = parse_profile_html(target.platform, html)
    bio_emails = extract_emails_from_html(profile.bio or "")
    bio_phones = extract_phones_from_html(profile.bio or "")
    links = profile.external_links

    link_semaphore = asyncio.Semaphore(LINK_CONCURRENCY)

    async def dig_link(link: str) -> tuple[list[str], list[str]]:
        async with link_semaphore:
            return await dig_url(client, link)

    dug = await asyncio.gather(*(dig_link(link) for link in links[:MAX_PROFILE_LINKS]))

    def unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                out.append(value)
        return out

    emails = unique((await mx_validate(bio_emails)) + [e for found, _ in dug for e in found])
    phones = unique(bio_phones + [p for _, found in dug for p in found])

    return DigResult(
        platform=target.platform,
        handle=identity["handle"],
        profile_url=identity["profile_url"],
        display_name=profile.display_name or identity["display_name"],
        follower_count=profile.follower_count,
        bio=profile.bio,
        emails=emails,
        phones=phones,
        links=links,
        status="found" if (emails or phones) else "no-email",
    )


async def dig_targets(
    targets: list[Target | None],
    entries: list[str],
    default_platform: str,
    on_result=None,
) -> list[DigResult]:
    """Dig every target with bounded concurrency, keeping one result per input
    row (including unresolved ones) so rows line up with the input.

    on_result, when given, is awaited after each row completes (for progress).
    """
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results: list[DigResult | None] = [None] * len(targets)

    async with make_client() as client:

        async def worker(index: int) -> None:
            target = targets[index]
            if target is None:
                result = DigResult(
                    platform=default_platform,
                    handle=str(entries[index]).strip(),
                    profile_url="",
                    status="unresolved",
                )
            else:
                async with semaphore:
                    result = await dig_creator(client, target)
            results[index] = result
            if on_result is not None:
                await on_result(index, result)

        await asyncio.gather(*(worker(i) for i in range(len(targets))))

    return [r for r in results if r is not None]
