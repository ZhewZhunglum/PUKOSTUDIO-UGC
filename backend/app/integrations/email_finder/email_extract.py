"""Email extraction/cleaning rules, port of creator-finder emailDig.mjs."""
import re
from urllib.parse import urlparse

BLOCKED_TLDS = {"css", "gif", "jpeg", "jpg", "js", "png", "svg", "webp"}
EMAIL_REGEX = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,24}\b", re.IGNORECASE)


def _clean_email(candidate: str) -> str | None:
    email = candidate.strip()
    email = re.sub(r"^[<(\"']+", "", email)
    email = re.sub(r"[>)\"',;:]+$", "", email)
    email = re.sub(r"\.+$", "", email).lower()
    tld = email.rsplit(".", 1)[-1] if "." in email else ""
    if not tld or tld in BLOCKED_TLDS:
        return None
    if not EMAIL_REGEX.fullmatch(email):
        return None
    return email


def extract_emails_from_html(html) -> list[str]:
    """Strip tags/entities and pull unique emails out of an HTML document."""
    if not isinstance(html, str) or not html:
        return []
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-f]+);", lambda m: chr(int(m.group(1), 16)), text, flags=re.IGNORECASE)
    text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)

    # Also catch mailto: links from the raw HTML (their href is lost once tags
    # are stripped, and the visible text may be obfuscated).
    mailtos = [m.group(1) for m in re.finditer(r"mailto:([^\"'\s>]+)", html, re.IGNORECASE)]
    found = EMAIL_REGEX.findall(text) + mailtos

    seen: set[str] = set()
    emails: list[str] = []
    for candidate in found:
        email = _clean_email(candidate)
        if email and email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


# --- phone / WhatsApp -------------------------------------------------------
# Conservative on purpose: wa.me / WhatsApp send links and tel: hrefs are
# unambiguous; free text only matches international (+ prefixed) numbers so
# follower counts and dates don't turn into "phones".
WA_LINK_REGEX = re.compile(
    r"(?:wa\.me/|api\.whatsapp\.com/send[^\"'\s>]*?phone=)\+?(\d{6,15})", re.IGNORECASE
)
TEL_LINK_REGEX = re.compile(r"tel:(\+?[\d\-().\s]{6,20}\d)", re.IGNORECASE)
INTL_PHONE_REGEX = re.compile(r"\+\d{1,4}(?:[\s\-.]?\(?\d{1,4}\)?){2,6}")


def _normalize_phone(candidate: str) -> str | None:
    digits = re.sub(r"\D", "", candidate)
    if not 7 <= len(digits) <= 15:
        return None
    return f"+{digits}"


def extract_phones_from_html(html) -> list[str]:
    """Phone/WhatsApp numbers from wa.me / tel: links and +international text."""
    if not isinstance(html, str) or not html:
        return []
    candidates: list[str] = []
    candidates.extend(m.group(1) for m in WA_LINK_REGEX.finditer(html))
    candidates.extend(m.group(1) for m in TEL_LINK_REGEX.finditer(html))
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    candidates.extend(m.group(0) for m in INTL_PHONE_REGEX.finditer(text))

    seen: set[str] = set()
    phones: list[str] = []
    for candidate in candidates:
        phone = _normalize_phone(candidate)
        if phone and phone not in seen:
            seen.add(phone)
            phones.append(phone)
    return phones


CONTACT_PATHS = ["contact", "contact-us", "about", "about-us", "info"]


def contact_urls_for(page_url: str) -> list[str]:
    """One level of likely same-origin contact-page URLs to crawl when the page
    itself yielded no email."""
    try:
        parsed = urlparse(page_url)
    except ValueError:
        return []
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return [f"{origin}/{path}" for path in CONTACT_PATHS]


def email_domains(emails: list[str]) -> list[str]:
    """Domains to run an MX lookup on, deduped, insertion order preserved."""
    seen: set[str] = set()
    domains: list[str] = []
    for email in emails:
        domain = email.split("@", 1)[1] if "@" in email else ""
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    return domains
