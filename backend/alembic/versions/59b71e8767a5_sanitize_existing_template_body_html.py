"""sanitize existing template body html

Data-only migration (no schema change). email_templates.body_html has never
been sanitized before this PR — it flowed straight from the API into the
column and straight from the column into outbound MIME. Run the same
sanitize_html() used by the new save paths over every existing row once, so
historical templates can't carry anything the new safety net would have
blocked had it existed when they were created.

signature_html is NOT backfilled here: every existing row was produced by
render_signature_html(), which HTML-escapes signature_content before
composing the block, so historical signature_html rows already contain no
unescaped user-authored markup — there is nothing unsafe to clean up.

Revision ID: 59b71e8767a5
Revises: 59d9217f6c8c
Create Date: 2026-07-08 18:26:23.440115

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.html_sanitize import sanitize_html

revision: str = '59b71e8767a5'
down_revision: Union[str, None] = '59d9217f6c8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_templates = sa.table(
    "email_templates",
    sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("body_html", sa.Text),
)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.select(_templates.c.id, _templates.c.body_html)).fetchall()
    for row in rows:
        cleaned = sanitize_html(row.body_html)
        if cleaned != (row.body_html or ""):
            bind.execute(
                _templates.update()
                .where(_templates.c.id == row.id)
                .values(body_html=cleaned)
            )


def downgrade() -> None:
    # Irreversible: the pre-sanitization HTML is not retained.
    pass
