import html as html_lib
import logging

from app.core.utils import strip_html
from app.integrations.email.base import EmailSender
from app.integrations.email.sendgrid_sender import SendGridSender
from app.integrations.email.ses_sender import SESSender
from app.integrations.email.smtp_sender import SMTPSender
from app.models.email_account import EmailAccount, EmailProviderType

logger = logging.getLogger(__name__)

# Sentinel wrapping the appended signature so apply_signature is idempotent and
# never double-appends across the reply / campaign send paths.
SIGNATURE_START = "<!--ugc-signature-->"
SIGNATURE_END = "<!--/ugc-signature-->"

_SENDER_CLASSES = {
    EmailProviderType.ses: SESSender,
    EmailProviderType.sendgrid: SendGridSender,
    EmailProviderType.smtp: SMTPSender,
}


def get_email_sender(account: EmailAccount) -> EmailSender:
    """Create an EmailSender instance for the given account."""
    sender_class = _SENDER_CLASSES.get(account.provider_type)
    if not sender_class:
        raise ValueError(f"Unknown email provider: {account.provider_type}")
    return sender_class(config=account.provider_config)


# Warmup ramp: the effective daily cap by warmup_stage. A fresh account (stage 0)
# is capped at 50/day and grows as the stage advances (see the advance_warmup
# beat task), never exceeding the account's configured daily_limit. Sending a
# lot from a cold domain/IP is the fastest way to get spam-filtered.
WARMUP_CAPS = [50, 100, 200, 350, 500, 750, 1000]


def effective_daily_limit(account: EmailAccount) -> int:
    """The lesser of the configured daily_limit and the current warmup cap."""
    stage = getattr(account, "warmup_stage", 0) or 0
    cap = WARMUP_CAPS[stage] if stage < len(WARMUP_CAPS) else account.daily_limit
    return min(account.daily_limit, cap)


def select_best_account(accounts: list[EmailAccount], to_domain: str | None = None) -> EmailAccount | None:
    """Select the best email account for sending.

    Strategy:
    1. Filter active, healthy, under-limit accounts (limit respects warmup ramp)
    2. Prefer accounts with most remaining daily capacity
    3. Prefer accounts not recently used for the target domain (when applicable)
    """
    eligible = [
        a for a in accounts
        if a.is_active
        and a.health_status.value == "healthy"
        and a.sent_today < effective_daily_limit(a)
    ]

    if not eligible:
        logger.warning("No eligible email accounts available for sending")
        return None

    # Sort by remaining capacity (most remaining first)
    eligible.sort(key=lambda a: effective_daily_limit(a) - a.sent_today, reverse=True)

    return eligible[0]


def unsubscribe_url(base_url: str, message_id: str, track_path: str = "track") -> str:
    # track_path lets a parallel pipeline (e.g. B2B client outreach) reuse this
    # builder under its own route prefix ("client-track") without touching the
    # influencer pipeline's default behavior.
    return f"{base_url}/api/v1/{track_path}/unsubscribe/{message_id}"


def unsubscribe_headers(base_url: str, message_id: str, track_path: str = "track") -> dict[str, str]:
    """RFC 8058 one-click unsubscribe headers — improve inbox placement."""
    url = unsubscribe_url(base_url, message_id, track_path)
    return {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def inject_unsubscribe(html_body: str, message_id: str, base_url: str, track_path: str = "track") -> str:
    """Append a visible unsubscribe footer (compliance + deliverability)."""
    url = unsubscribe_url(base_url, message_id, track_path)
    footer = (
        '<div style="margin-top:16px;font-size:12px;color:#9ca3af;'
        'font-family:Arial,Helvetica,sans-serif">'
        f'若不想再收到此类邮件，可<a href="{url}" style="color:#9ca3af">点此退订</a>。'
        "</div>"
    )
    if "</body>" in html_body:
        return html_body.replace("</body>", f"{footer}</body>")
    return html_body + footer


def render_signature_html(
    *,
    content: str | None,
    logo_url: str | None,
    brand_color: str | None,
    social_links: dict | None,
) -> str:
    """Render the canonical branded signature block from structured inputs.

    ``content`` is treated as plain text (HTML-escaped, newlines -> <br>) so the
    stored signature can never carry injected markup. The block uses the brand
    color as a left accent bar and renders the logo + social links when present.
    """
    accent = brand_color if brand_color else "#d97706"
    parts: list[str] = []
    if logo_url:
        parts.append(
            f'<img src="{html_lib.escape(logo_url, quote=True)}" alt="logo" '
            f'style="max-height:48px;margin-bottom:8px;border:0;display:block" />'
        )
    if content:
        safe = html_lib.escape(content).replace("\n", "<br />")
        parts.append(f'<div style="color:#374151">{safe}</div>')
    if social_links:
        links = []
        for label, url in social_links.items():
            if not url:
                continue
            links.append(
                f'<a href="{html_lib.escape(str(url), quote=True)}" '
                f'style="color:{html_lib.escape(accent, quote=True)};text-decoration:none;'
                f'margin-right:12px">{html_lib.escape(str(label))}</a>'
            )
        if links:
            parts.append(f'<div style="margin-top:8px;font-size:13px">{"".join(links)}</div>')

    inner = "".join(parts) or ""
    return (
        f'<div style="margin-top:24px;padding:12px 0 0 14px;'
        f'border-left:3px solid {html_lib.escape(accent, quote=True)};'
        f'font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5">'
        f"{inner}</div>"
    )


def apply_signature(
    html_body: str,
    text_body: str | None,
    account: EmailAccount,
) -> tuple[str, str | None]:
    """Append the account's branded signature to an outbound body.

    Idempotent (guards on the sentinel) and a no-op when the account has no
    enabled signature. MUST be called before inject_tracking so the tracking
    pixel ends up after the signature.
    """
    signature_html = getattr(account, "signature_html", None)
    if not getattr(account, "signature_enabled", False) or not signature_html:
        return html_body, text_body
    if SIGNATURE_START in html_body:
        return html_body, text_body

    block = f"{SIGNATURE_START}{signature_html}{SIGNATURE_END}"
    if "</body>" in html_body:
        new_html = html_body.replace("</body>", f"{block}</body>")
    else:
        new_html = f"{html_body}{block}"

    new_text = text_body
    if text_body is not None:
        signature_text = strip_html(signature_html)
        new_text = f"{text_body}\n\n-- \n{signature_text}" if signature_text else text_body

    return new_html, new_text


def inject_tracking(html_body: str, message_id: str, base_url: str, track_path: str = "track") -> str:
    """Inject open tracking pixel into HTML body."""
    pixel = f'<img src="{base_url}/api/v1/{track_path}/open/{message_id}.png" width="1" height="1" style="display:none" />'

    if "</body>" in html_body:
        return html_body.replace("</body>", f"{pixel}</body>")
    return html_body + pixel


def rewrite_links_for_tracking(
    html_body: str, message_id: str, base_url: str, track_path: str = "track"
) -> str:
    """Rewrite outbound <a href> targets to route through a click redirect.

    A click is a much stronger "a human engaged" signal than the open pixel:
    Apple Mail Privacy Protection (and other prefetching clients) fetch the
    open pixel automatically at delivery time regardless of whether anyone
    ever reads the mail, silently inflating open_rate. A click can't be
    triggered that way, so it gives campaign_service a corroborating signal.

    Call this BEFORE inject_unsubscribe, so the unsubscribe footer link
    (added afterward) is never itself wrapped in a tracking redirect — no
    special-casing needed to identify and skip it.

    Best-effort: any parse failure returns the body unchanged rather than
    risking a broken send over a tracking feature.
    """
    if "<a " not in html_body and "<a\n" not in html_body and "<a\t" not in html_body:
        return html_body  # no links at all — skip the parse

    from urllib.parse import quote

    from lxml import html as lxml_html

    try:
        tree = lxml_html.fromstring(html_body)
    except Exception as exc:
        logger.warning("Skipping click-tracking rewrite for %s: %s", message_id, exc)
        return html_body

    changed = False
    for anchor in tree.iter("a"):
        href = anchor.get("href")
        if not href or href.startswith(("mailto:", "tel:", "#")):
            continue
        redirect = f"{base_url}/api/v1/{track_path}/click/{message_id}?url={quote(href, safe='')}"
        anchor.set("href", redirect)
        changed = True

    if not changed:
        return html_body
    return lxml_html.tostring(tree, encoding="unicode")


def finalize_html_for_send(html: str) -> str:
    """Inline CSS (style blocks / classes) into element style= attributes.

    MUST run last, immediately before sender.send(), after signature/
    unsubscribe/tracking injection — Gmail, Outlook, and Apple Mail strip or
    ignore <style> blocks and many class-based selectors, so WYSIWYG output
    (which may carry a <style> block from pasted rich content) needs inlining
    to render consistently. Idempotent: running it twice on already-inlined
    HTML is a safe no-op.
    """
    from premailer import Premailer

    return Premailer(
        html,
        remove_classes=False,
        keep_style_tags=False,
        strip_important=False,
        cssutils_logging_level="CRITICAL",
    ).transform()
