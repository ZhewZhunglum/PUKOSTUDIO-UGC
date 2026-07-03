#!/usr/bin/env python3
"""
Seed the team-scoped multilingual template library.

Usage:
    cd backend && python scripts/seed_library_templates.py --team-id <uuid>
    python scripts/seed_library_templates.py --team-email admin@example.com
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.template import EmailTemplate, TemplateCategory
from app.models.user import User
from app.services.template_service import extract_variables

DATABASE_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://ugc:ugc_password@localhost:5432/ugc_db",
)


LIBRARY_TEMPLATES = [
    {
        "name": "Friendly UGC Outreach",
        "language": "en",
        "category": TemplateCategory.initial_outreach,
        "subject": "Hi {{first_name}}, collaboration idea for {{platform}}",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>I came across your {{platform}} content and loved how you cover {{niche}}.</p>"
            "<p>We are looking for creators to try {{product_name}} and share authentic UGC. "
            "Would you be open to hearing the brief?</p>"
            "<p>Best,<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Friendly UGC Outreach",
        "language": "zh",
        "category": TemplateCategory.initial_outreach,
        "subject": "{{first_name}}，想和你聊聊 {{platform}} 合作",
        "body_html": (
            "<p>Hi {{first_name}}，</p>"
            "<p>我们看到了你在 {{platform}} 上关于 {{niche}} 的内容，很喜欢你的表达方式。</p>"
            "<p>我们正在为 {{product_name}} 寻找真实、有质感的 UGC 创作者，想了解你是否愿意看看合作 brief？</p>"
            "<p>祝好，<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Gentle Follow-up 1",
        "language": "en",
        "category": TemplateCategory.followup_1,
        "subject": "Following up on {{product_name}}",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>Just wanted to gently follow up on my note about {{product_name}}.</p>"
            "<p>Your {{platform}} audience feels like a strong fit, and I would be happy to send over "
            "the details if you are interested.</p>"
            "<p>Best,<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Gentle Follow-up 1",
        "language": "zh",
        "category": TemplateCategory.followup_1,
        "subject": "跟进一下 {{product_name}} 合作",
        "body_html": (
            "<p>Hi {{first_name}}，</p>"
            "<p>想轻轻跟进一下之前关于 {{product_name}} 的合作邀请。</p>"
            "<p>你的 {{platform}} 受众和我们的产品方向很匹配，如果你感兴趣，我可以把合作细节发给你。</p>"
            "<p>祝好，<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Final Follow-up",
        "language": "en",
        "category": TemplateCategory.followup_2,
        "subject": "Last note about a possible collaboration",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>I will close the loop after this note. We would still love to explore a collaboration "
            "around {{product_name}} if the timing works for you.</p>"
            "<p>Either way, thanks for creating thoughtful {{niche}} content.</p>"
            "<p>Best,<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Final Follow-up",
        "language": "zh",
        "category": TemplateCategory.followup_2,
        "subject": "最后跟进一次合作可能",
        "body_html": (
            "<p>Hi {{first_name}}，</p>"
            "<p>这是最后一次跟进 {{product_name}} 的合作邀请。如果近期时间合适，我们仍然很希望和你聊聊。</p>"
            "<p>无论如何，也感谢你持续创作有价值的 {{niche}} 内容。</p>"
            "<p>祝好，<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Positive Reply",
        "language": "en",
        "category": TemplateCategory.reply,
        "subject": "Re: {{product_name}} collaboration",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>Thanks for getting back to us. Great to hear you are interested.</p>"
            "<p>I can share the brief, deliverables, timeline, and sample policy next so you can review "
            "whether this is a fit.</p>"
            "<p>Best,<br>{{sender_name}}</p>"
        ),
    },
    {
        "name": "Positive Reply",
        "language": "zh",
        "category": TemplateCategory.reply,
        "subject": "Re: {{product_name}} 合作",
        "body_html": (
            "<p>Hi {{first_name}}，</p>"
            "<p>谢谢回复，很高兴你对合作感兴趣。</p>"
            "<p>我可以接下来发你 brief、交付内容、时间线和样品安排，你看完后再判断是否合适。</p>"
            "<p>祝好，<br>{{sender_name}}</p>"
        ),
    },
]


def resolve_team_id(session: Session, team_id: str | None, team_email: str | None) -> uuid.UUID:
    if team_id:
        return uuid.UUID(team_id)
    if team_email:
        user = session.execute(select(User).where(User.email == team_email)).scalar_one_or_none()
        if not user:
            raise SystemExit(f"No user found for --team-email {team_email}")
        return user.team_id
    raise SystemExit("Provide --team-id or --team-email")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id")
    parser.add_argument("--team-email")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    with Session(engine) as session:
        team_id = resolve_team_id(session, args.team_id, args.team_email)
        created = 0

        for item in LIBRARY_TEMPLATES:
            exists = session.execute(
                select(EmailTemplate).where(
                    EmailTemplate.team_id == team_id,
                    EmailTemplate.name == item["name"],
                    EmailTemplate.language == item["language"],
                    EmailTemplate.is_library.is_(True),
                )
            ).scalar_one_or_none()
            if exists:
                continue

            variables = extract_variables(item["subject"] + " " + item["body_html"])
            session.add(
                EmailTemplate(
                    team_id=team_id,
                    name=item["name"],
                    subject=item["subject"],
                    body_html=item["body_html"],
                    body_text=None,
                    category=item["category"],
                    language=item["language"],
                    is_library=True,
                    variables={"fields": variables},
                )
            )
            created += 1

        if args.dry_run:
            session.rollback()
        else:
            session.commit()
        print(f"{'Would create' if args.dry_run else 'Created'} {created} library templates")


if __name__ == "__main__":
    main()
