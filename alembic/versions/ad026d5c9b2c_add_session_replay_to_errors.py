"""add_session_replay_to_errors

Revision ID: ad026d5c9b2c
Revises: 63e7215f6f2f
Create Date: 2026-07-20 18:13:41.917500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad026d5c9b2c'
down_revision: Union[str, Sequence[str], None] = '63e7215f6f2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('errors', sa.Column('session_replay', sa.JSON, nullable=True))
    op.add_column('errors', sa.Column('has_session_replay', sa.Boolean, server_default='f', nullable=False))

def downgrade():
    op.drop_column('errors', 'has_session_replay')
    op.drop_column('errors', 'session_replay')
