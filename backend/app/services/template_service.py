import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.html_sanitize import sanitize_html
from app.models.template import EmailTemplate, TemplateCategory
from app.schemas.template import TemplateCreate, TemplateUpdate


async def list_templates(db: AsyncSession, team_id: uuid.UUID) -> list[EmailTemplate]:
    result = await db.execute(
        select(EmailTemplate)
        .where(EmailTemplate.team_id == team_id, EmailTemplate.is_library.is_(False))
        .order_by(EmailTemplate.created_at.desc())
    )
    return list(result.scalars().all())


async def list_library_templates(
    db: AsyncSession, team_id: uuid.UUID, language: str | None = None
) -> list[EmailTemplate]:
    query = select(EmailTemplate).where(
        EmailTemplate.team_id == team_id,
        EmailTemplate.is_library.is_(True),
    )
    if language:
        query = query.where(EmailTemplate.language == language)
    result = await db.execute(query.order_by(EmailTemplate.category, EmailTemplate.name))
    return list(result.scalars().all())


async def get_template(
    db: AsyncSession, template_id: uuid.UUID, team_id: uuid.UUID
) -> EmailTemplate:
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id, EmailTemplate.team_id == team_id
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundException("Template not found")
    return template


async def create_template(
    db: AsyncSession, team_id: uuid.UUID, data: TemplateCreate
) -> EmailTemplate:
    body_html = sanitize_html(data.body_html)
    # Auto-extract variables from template
    variables = extract_variables(data.subject + " " + body_html)

    template = EmailTemplate(
        team_id=team_id,
        name=data.name,
        subject=data.subject,
        body_html=body_html,
        body_text=data.body_text,
        category=TemplateCategory(data.category),
        language=data.language,
        is_library=False,
        variables={"fields": variables} if variables else data.variables,
    )
    db.add(template)
    await db.flush()
    return template


async def update_template(
    db: AsyncSession, template_id: uuid.UUID, team_id: uuid.UUID, data: TemplateUpdate
) -> EmailTemplate:
    template = await get_template(db, template_id, team_id)
    if template.is_library:
        raise BadRequestException("Library templates must be cloned before editing")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "category" and value is not None:
            setattr(template, field, TemplateCategory(value))
        elif field == "is_library":
            continue
        elif field == "body_html" and value is not None:
            setattr(template, field, sanitize_html(value))
        else:
            setattr(template, field, value)

    # Re-extract variables if content changed
    if data.subject is not None or data.body_html is not None:
        text = (template.subject or "") + " " + (template.body_html or "")
        variables = extract_variables(text)
        template.variables = {"fields": variables} if variables else template.variables

    await db.flush()
    return template


_VALID_TEMPLATE_CATEGORIES = {c.value for c in TemplateCategory}

# Column order used for both import parsing and export generation.
TEMPLATE_EXPORT_COLUMNS = ["name", "subject", "body_html", "body_text", "category", "language"]


async def import_templates_from_rows(
    db: AsyncSession, team_id: uuid.UUID, rows: list[dict]
) -> dict:
    """Create templates from parsed spreadsheet rows.

    Requires name/subject/body_html per row; unknown categories fall back to
    'custom'. Each row runs in its own SAVEPOINT so a single bad row is skipped
    without discarding the rows already staged.
    """
    imported = 0
    skipped = 0
    for row in rows:
        name = (row.get("name") or "").strip()
        subject = (row.get("subject") or "").strip()
        body_html = (row.get("body_html") or "").strip()
        if not name or not subject or not body_html:
            skipped += 1
            continue

        category = (row.get("category") or "").strip() or "initial_outreach"
        if category not in _VALID_TEMPLATE_CATEGORIES:
            category = "custom"
        language = (row.get("language") or "").strip() or "en"
        body_text = (row.get("body_text") or "").strip() or None

        try:
            async with db.begin_nested():
                await create_template(
                    db,
                    team_id,
                    TemplateCreate(
                        name=name,
                        subject=subject,
                        body_html=body_html,
                        body_text=body_text,
                        category=category,
                        language=language,
                    ),
                )
            imported += 1
        except Exception:
            skipped += 1

    await db.flush()
    return {"imported": imported, "skipped": skipped}


async def clone_template(
    db: AsyncSession, template_id: uuid.UUID, team_id: uuid.UUID
) -> EmailTemplate:
    source = await get_template(db, template_id, team_id)
    clone_data = TemplateCreate(
        name=f"{source.name} Copy",
        subject=source.subject,
        body_html=source.body_html,
        body_text=source.body_text,
        category=source.category.value,
        language=source.language,
        is_library=False,
        variables=source.variables,
    )
    return await create_template(db, team_id, clone_data)


async def delete_template(
    db: AsyncSession, template_id: uuid.UUID, team_id: uuid.UUID
) -> None:
    template = await get_template(db, template_id, team_id)
    if template.is_library:
        raise BadRequestException("Library templates cannot be deleted")
    await db.delete(template)


def extract_variables(text: str) -> list[str]:
    """Extract {{variable}} placeholders from text."""
    return list(set(re.findall(r"\{\{(\w+)\}\}", text)))


def build_influencer_variables(influencer, fallback_name: str | None = None) -> dict:
    """Assemble the template variable map for an outbound email.

    Covers every placeholder the product documents ({{name}}, {{first_name}},
    {{email}}, {{niche}}, {{country}}, {{platform}}, {{username}}, {{followers}}).
    ``influencer`` may be None (falls back to ``fallback_name``); platform-derived
    values come from the influencer's first linked platform when present.
    """
    name = (getattr(influencer, "name", None) or fallback_name or "").strip()
    first_name = name.split()[0] if name else ""

    platforms = getattr(influencer, "platforms", None) or []
    first_platform = platforms[0] if platforms else None

    def _platform_field(attr: str) -> str:
        value = getattr(first_platform, attr, None) if first_platform else None
        if value is None:
            return ""
        # Platform enum -> its string value; everything else -> str()
        return str(getattr(value, "value", value))

    return {
        "name": name,
        "first_name": first_name,
        "email": getattr(influencer, "email", None) or "",
        "niche": getattr(influencer, "niche", None) or "",
        "country": getattr(influencer, "country", None) or "",
        "platform": _platform_field("platform"),
        "username": _platform_field("username"),
        "followers": _platform_field("followers"),
    }


def render_template(subject: str, body_html: str, variables: dict) -> tuple[str, str]:
    """Replace {{variable}} placeholders with actual values."""
    rendered_subject = subject
    rendered_body = body_html

    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        rendered_subject = rendered_subject.replace(placeholder, str(value))
        rendered_body = rendered_body.replace(placeholder, str(value))

    return rendered_subject, rendered_body


# ── Template conversion ────────────────────────────────────────────────────────

# Ordered from most-specific to least-specific so substitution doesn't double-hit.
_RULE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Explicit bracket-style placeholders
    (re.compile(r"\[(?:full[\s_-]?)?name\]", re.I), "{{name}}"),
    (re.compile(r"\[(?:first[\s_-]?)?name\]", re.I), "{{first_name}}"),
    (re.compile(r"\[@?user(?:name)?\]", re.I), "{{username}}"),
    (re.compile(r"\[(?:your[\s_-]?)?niche\]", re.I), "{{niche}}"),
    (re.compile(r"\[(?:your[\s_-]?)?platform\]", re.I), "{{platform}}"),
    (re.compile(r"\[(?:follower[s]?(?:[\s_-]?count)?)\]", re.I), "{{followers}}"),
    (re.compile(r"\[email\]", re.I), "{{email}}"),
    # Angle-bracket / double-angle variants: <<Name>>, <Name>
    (re.compile(r"<<(?:full[\s_-]?)?name>>", re.I), "{{name}}"),
    (re.compile(r"<<(?:first[\s_-]?)?name>>", re.I), "{{first_name}}"),
    (re.compile(r"<<(?:your[\s_-]?)?niche>>", re.I), "{{niche}}"),
    # Greeting patterns: "Hi Jane," / "Hello Sarah," / "Dear Creator,"
    (re.compile(r"(?i)(\b(?:Hi|Hey|Hello|Dear)\s+)([A-Z][a-z]+)(?=[,\s!])"), r"\g<1>{{first_name}}"),
]

_PLAIN_TO_HTML_RE = re.compile(r"\n{2,}")


def _plain_to_html(text: str) -> str:
    """Wrap double-newline separated paragraphs in <p> tags."""
    # If already looks like HTML, leave it
    if re.search(r"<[a-z]+[\s>]", text, re.I):
        return text
    paras = _PLAIN_TO_HTML_RE.split(text.strip())
    return "".join(f"<p>{p.strip().replace(chr(10), '<br>')}</p>" for p in paras if p.strip())


def rule_convert(raw_subject: str, raw_body: str) -> dict:
    """Deterministic variable substitution using regex rules."""
    subject = raw_subject
    body = raw_body

    for pattern, replacement in _RULE_PATTERNS:
        subject = pattern.sub(replacement, subject)
        body = pattern.sub(replacement, body)

    body_html = _plain_to_html(body)
    used_vars = extract_variables(subject + " " + body_html)
    return {"subject": subject, "body_html": body_html, "variables": used_vars, "method": "rule"}


async def ai_convert(raw_subject: str, raw_body: str, ai_config: dict | None = None) -> dict:
    """Use the configured AI provider to intelligently convert the template."""
    from app.integrations.ai.factory import get_ai_provider

    provider = get_ai_provider(ai_config)
    parsed = await provider.convert_template(raw_subject, raw_body)
    subject = parsed.get("subject", raw_subject)
    body_html = parsed.get("body_html", _plain_to_html(raw_body))
    variables = parsed.get("variables") or extract_variables(subject + " " + body_html)
    return {"subject": subject, "body_html": body_html, "variables": variables, "method": "ai"}
