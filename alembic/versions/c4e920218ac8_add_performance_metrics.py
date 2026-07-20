"""add_performance_metrics

Revision ID: c4e920218ac8
Revises: ad026d5c9b2c
Create Date: 2026-07-20 22:35:26.947036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = 'c4e920218ac8'
down_revision: Union[str, Sequence[str], None] = 'ad026d5c9b2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'performance_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('method', sa.String(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=False),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('metrics', JSON, nullable=True),
        sa.Column('environment', sa.String(), nullable=False),
        sa.Column('release_version', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('user_email', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('performance_metrics')