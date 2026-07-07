"""add email suppressions

Revision ID: 5641dfa5cbe1
Revises: e7b4a2c9d6f1
Create Date: 2026-07-07 13:09:50.860535

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5641dfa5cbe1'
down_revision: Union[str, None] = 'e7b4a2c9d6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_suppressions',
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column(
            'reason',
            sa.Enum('bounced', 'complained', 'unsubscribed', 'manual', name='suppressionreason'),
            nullable=False,
        ),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'email', name='uq_email_suppressions_team_email'),
    )
    op.create_index(op.f('ix_email_suppressions_email'), 'email_suppressions', ['email'], unique=False)
    op.create_index(op.f('ix_email_suppressions_team_id'), 'email_suppressions', ['team_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_email_suppressions_team_id'), table_name='email_suppressions')
    op.drop_index(op.f('ix_email_suppressions_email'), table_name='email_suppressions')
    op.drop_table('email_suppressions')
