"""add_email_verification_fields

Revision ID: 4af3454d1531
Revises: c4e920218ac8
Create Date: 2026-07-31 05:37:29.176796

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4af3454d1531'
down_revision: Union[str, Sequence[str], None] = 'c4e920218ac8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('email_verification_expires', sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column('users', 'email_verification_expires')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'is_email_verified')
