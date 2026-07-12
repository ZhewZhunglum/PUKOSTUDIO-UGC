"""add email dig jobs

Revision ID: 7e1c9a4b2d3f
Revises: 2320bf5cffcb
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7e1c9a4b2d3f"
down_revision: Union[str, None] = "2320bf5cffcb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    email_dig_job_status = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        name="emaildigjobstatus",
        create_type=False,
    )
    email_dig_job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "email_dig_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("status", email_dig_job_status, nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="dig"),
        sa.Column("default_platform", sa.String(length=20), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("resolved_count", sa.Integer(), nullable=False),
        sa.Column("found_count", sa.Integer(), nullable=False),
        sa.Column("phone_found_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_dig_jobs_team_id"), "email_dig_jobs", ["team_id"], unique=False)
    op.create_index(op.f("ix_email_dig_jobs_status"), "email_dig_jobs", ["status"], unique=False)

    # Dig results write back onto influencers: phone/WhatsApp plus a marker for
    # "already dug, nothing found" so the UI can flag them.
    op.add_column("influencers", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("influencers", sa.Column("email_source", sa.String(length=20), nullable=True))
    op.add_column("influencers", sa.Column("phone_source", sa.String(length=20), nullable=True))
    op.add_column("influencers", sa.Column("email_dig_status", sa.String(length=20), nullable=True))
    op.add_column("influencers", sa.Column("email_dig_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("influencers", "phone_source")
    op.drop_column("influencers", "email_source")
    op.drop_column("influencers", "email_dig_at")
    op.drop_column("influencers", "email_dig_status")
    op.drop_column("influencers", "phone")
    op.drop_index(op.f("ix_email_dig_jobs_status"), table_name="email_dig_jobs")
    op.drop_index(op.f("ix_email_dig_jobs_team_id"), table_name="email_dig_jobs")
    op.drop_table("email_dig_jobs")
    sa.Enum(name="emaildigjobstatus").drop(op.get_bind(), checkfirst=True)
