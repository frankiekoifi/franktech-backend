"""add_password_reset_fields

Revision ID: 7cf6e073ab9a
Revises: 4af3454d1531
Create Date: 2026-07-31 05:58:20.962779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cf6e073ab9a'
down_revision: Union[str, Sequence[str], None] = '4af3454d1531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('users', sa.Column('reset_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('reset_token_expires', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'reset_token_expires')
    op.drop_column('users', 'reset_token')
