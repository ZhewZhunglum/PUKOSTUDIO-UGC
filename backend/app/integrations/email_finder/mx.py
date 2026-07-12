"""MX validation with fail-open semantics, port of creator-finder index.mjs.

Only a definitive "this domain has no MX" answer discards an email; resolver
failures (proxied/TUN networks often refuse MX queries entirely) keep it.
"""
import asyncio

import dns.asyncresolver
import dns.exception
import dns.resolver

from app.integrations.email_finder.email_extract import email_domains

# Public DNS to retry through when the system resolver refuses/fails.
FALLBACK_DNS = ["223.5.5.5", "119.29.29.29"]

# Exceptions meaning "the domain genuinely has no MX", as opposed to "the
# resolver itself failed".
_NO_MX_EXCEPTIONS = (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer)

_mx_cache: dict[str, bool] = {}
_fallback_resolver: dns.asyncresolver.Resolver | None = None


def clear_cache() -> None:
    _mx_cache.clear()


async def _resolve_mx(resolver: dns.asyncresolver.Resolver, domain: str) -> bool:
    answer = await resolver.resolve(domain, "MX")
    return len(answer) > 0


async def domain_has_mx(domain: str) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]
    ok = True  # fail-open
    try:
        ok = await _resolve_mx(dns.asyncresolver.Resolver(), domain)
    except _NO_MX_EXCEPTIONS:
        ok = False
    except (dns.exception.DNSException, OSError, asyncio.TimeoutError):
        global _fallback_resolver
        try:
            if _fallback_resolver is None:
                _fallback_resolver = dns.asyncresolver.Resolver(configure=False)
                _fallback_resolver.nameservers = FALLBACK_DNS
            ok = await _resolve_mx(_fallback_resolver, domain)
        except _NO_MX_EXCEPTIONS:
            ok = False
        except (dns.exception.DNSException, OSError, asyncio.TimeoutError):
            ok = True
    _mx_cache[domain] = ok
    return ok


async def mx_validate(emails: list[str]) -> list[str]:
    """Keep only emails whose domain has (or may have) MX records, deduped."""
    valid: list[str] = []
    for domain in email_domains(emails):
        if await domain_has_mx(domain):
            valid.extend(email for email in emails if email.endswith(f"@{domain}"))
    seen: set[str] = set()
    out: list[str] = []
    for email in valid:
        if email not in seen:
            seen.add(email)
            out.append(email)
    return out
