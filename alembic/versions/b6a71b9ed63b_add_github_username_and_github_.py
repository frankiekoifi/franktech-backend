"""Add github_username and github_connected_at

Revision ID: b6a71b9ed63b
Revises: 48bfd4a529bb
Create Date: 2026-07-13 16:34:42.412996

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6a71b9ed63b'
down_revision: Union[str, Sequence[str], None] = '48bfd4a529bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('github_username', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('github_connected_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'github_connected_at')
    op.drop_column('users', 'github_username')