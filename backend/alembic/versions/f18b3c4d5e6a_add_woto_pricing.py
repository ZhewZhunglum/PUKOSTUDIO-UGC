"""add woto pricing

Revision ID: f18b3c4d5e6a
Revises: 9d2a4e1f7b6c
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "f18b3c4d5e6a"
down_revision: Union[str, None] = "9d2a4e1f7b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    billing_operation = postgresql.ENUM(
        "influencer_search",
        "influencer_detail",
        "video_data",
        "contact_email",
        "brand_monitoring",
        name="wotobillingoperation",
        create_type=False,
    )
    billing_operation.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "woto_sync_jobs",
        sa.Column(
            "estimated_cost_cny",
            sa.Numeric(12, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "woto_sync_jobs",
        sa.Column(
            "actual_cost_cny",
            sa.Numeric(12, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "woto_sync_jobs",
        sa.Column("billable_search_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "woto_sync_jobs",
        sa.Column("billable_detail_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "woto_sync_jobs",
        sa.Column("billable_contact_calls", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )

    op.create_table(
        "woto_usage_records",
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("sync_job_id", sa.UUID(), nullable=True),
        sa.Column("operation", billing_operation, nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("dedupe_key", sa.String(length=500), nullable=True),
        sa.Column("unit_count", sa.Integer(), nullable=False),
        sa.Column("unit_price_cny", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("amount_cny", sa.Numeric(12, 2), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sync_job_id"], ["woto_sync_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_woto_usage_records_billable"), "woto_usage_records", ["billable"], unique=False)
    op.create_index(op.f("ix_woto_usage_records_dedupe_key"), "woto_usage_records", ["dedupe_key"], unique=False)
    op.create_index(op.f("ix_woto_usage_records_operation"), "woto_usage_records", ["operation"], unique=False)
    op.create_index(op.f("ix_woto_usage_records_platform"), "woto_usage_records", ["platform"], unique=False)
    op.create_index(op.f("ix_woto_usage_records_sync_job_id"), "woto_usage_records", ["sync_job_id"], unique=False)
    op.create_index(op.f("ix_woto_usage_records_team_id"), "woto_usage_records", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_woto_usage_records_team_id"), table_name="woto_usage_records")
    op.drop_index(op.f("ix_woto_usage_records_sync_job_id"), table_name="woto_usage_records")
    op.drop_index(op.f("ix_woto_usage_records_platform"), table_name="woto_usage_records")
    op.drop_index(op.f("ix_woto_usage_records_operation"), table_name="woto_usage_records")
    op.drop_index(op.f("ix_woto_usage_records_dedupe_key"), table_name="woto_usage_records")
    op.drop_index(op.f("ix_woto_usage_records_billable"), table_name="woto_usage_records")
    op.drop_table("woto_usage_records")

    op.drop_column("woto_sync_jobs", "billable_contact_calls")
    op.drop_column("woto_sync_jobs", "billable_detail_calls")
    op.drop_column("woto_sync_jobs", "billable_search_calls")
    op.drop_column("woto_sync_jobs", "actual_cost_cny")
    op.drop_column("woto_sync_jobs", "estimated_cost_cny")

    sa.Enum(name="wotobillingoperation").drop(op.get_bind(), checkfirst=True)
