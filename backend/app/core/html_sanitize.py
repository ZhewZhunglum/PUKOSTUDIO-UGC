"""Email-safe HTML sanitization for user-authored rich text.

Applied on every save path that persists rich HTML written through the
WYSIWYG editor (custom signature_html, template body_html, conversation
reply body_html). nh3 (Rust/ammonia) drops disallowed tags/attributes and
rewrites disallowed URL schemes instead of raising, so callers never need a
try/except.

Trust model: this product is an internal outreach tool — only authenticated
team members author this HTML (never public/UGC input) — so we sanitize
against XSS-by-accident (a stray pasted <script>, an onerror= handler picked
up from a copy-pasted webpage) rather than a hostile-author threat model.
nh3's attribute allowlist controls attribute *names* only; it does not parse
CSS *values* inside style="" attributes, so a deliberately hostile author
could still craft `style="position:fixed"` or similar — an accepted risk
given the trust model above, not an oversight.
"""
import nh3

_ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "a",
    "img", "ul", "ol", "li",
    "span", "div",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote",
    "table", "thead", "tbody", "tr", "td", "th",
}

# Every block/inline container that Tiptap can attach inline style="" to
# (e.g. its TextAlign extension sets style="text-align:..." directly on <p>
# and heading tags) must allow "style", or formatting silently vanishes on
# the next save.
_STYLEABLE = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "span", "div", "table", "blockquote"}

_ALLOWED_ATTRIBUTES = {
    # "rel" is deliberately excluded: nh3 manages it itself when link_rel is
    # set below, and raises if "rel" also appears in the allowlist.
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height", "style"},
    "td": {"style", "colspan", "rowspan"},
    "th": {"style", "colspan", "rowspan"},
    **{tag: {"style"} for tag in _STYLEABLE},
}

_ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_html(html: str | None) -> str:
    """Strip everything outside the email-safe allowlist. None/"" -> ""."""
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
    )
