"""add woto sync

Revision ID: 9d2a4e1f7b6c
Revises: 4c91a7d2e6b3
Create Date: 2026-05-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "9d2a4e1f7b6c"
down_revision: Union[str, None] = "4c91a7d2e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    woto_sync_job_status = postgresql.ENUM(
        "queued",
        "running",
        "completed",
        "failed",
        name="wotosyncjobstatus",
        create_type=False,
    )
    woto_sync_job_status.create(op.get_bind(), checkfirst=True)

    op.add_column("influencer_platforms", sa.Column("team_id", sa.UUID(), nullable=True))
    op.add_column("influencer_platforms", sa.Column("data_provider", sa.String(length=50), nullable=True))
    op.add_column("influencer_platforms", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column(
        "influencer_platforms",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE influencer_platforms AS ip
        SET team_id = influencers.team_id
        FROM influencers
        WHERE influencers.id = ip.influencer_id
        """
    )
    op.alter_column("influencer_platforms", "team_id", nullable=False)
    op.create_foreign_key(
        "fk_influencer_platforms_team_id_teams",
        "influencer_platforms",
        "teams",
        ["team_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_influencer_platforms_team_id"),
        "influencer_platforms",
        ["team_id"],
        unique=False,
    )
    op.create_index(
        "ix_influencer_platforms_provider_external",
        "influencer_platforms",
        ["data_provider", "platform", "external_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_influencer_platforms_team_provider_platform_external",
        "influencer_platforms",
        ["team_id", "data_provider", "platform", "external_id"],
    )

    op.create_table(
        "woto_sync_jobs",
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("query", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", woto_sync_job_status, nullable=False),
        sa.Column("discovered", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("enrolled_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("warning_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_woto_sync_jobs_campaign_id"), "woto_sync_jobs", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_woto_sync_jobs_platform"), "woto_sync_jobs", ["platform"], unique=False)
    op.create_index(op.f("ix_woto_sync_jobs_status"), "woto_sync_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_woto_sync_jobs_team_id"), "woto_sync_jobs", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_woto_sync_jobs_team_id"), table_name="woto_sync_jobs")
    op.drop_index(op.f("ix_woto_sync_jobs_status"), table_name="woto_sync_jobs")
    op.drop_index(op.f("ix_woto_sync_jobs_platform"), table_name="woto_sync_jobs")
    op.drop_index(op.f("ix_woto_sync_jobs_campaign_id"), table_name="woto_sync_jobs")
    op.drop_table("woto_sync_jobs")

    op.drop_constraint(
        "uq_influencer_platforms_team_provider_platform_external",
        "influencer_platforms",
        type_="unique",
    )
    op.drop_index("ix_influencer_platforms_provider_external", table_name="influencer_platforms")
    op.drop_index(op.f("ix_influencer_platforms_team_id"), table_name="influencer_platforms")
    op.drop_constraint(
        "fk_influencer_platforms_team_id_teams",
        "influencer_platforms",
        type_="foreignkey",
    )
    op.drop_column("influencer_platforms", "last_synced_at")
    op.drop_column("influencer_platforms", "external_id")
    op.drop_column("influencer_platforms", "data_provider")
    op.drop_column("influencer_platforms", "team_id")

    sa.Enum(name="wotosyncjobstatus").drop(op.get_bind(), checkfirst=True)
