"""Add organization teams and invites

Revision ID: cd5cb41a6eca
Revises: b6a71b9ed63b
Create Date: 2026-07-16 17:30:52.241513

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd5cb41a6eca'
down_revision: Union[str, Sequence[str], None] = 'b6a71b9ed63b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('organization_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('invited_by', sa.Integer(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index(op.f('ix_organization_invites_id'), 'organization_invites', ['id'], unique=False)
    
    op.add_column('organizations', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.execute("UPDATE organizations SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1)")
    
    op.add_column('users', sa.Column('email_notifications', sa.Boolean(), nullable=True, server_default='1'))
    op.add_column('users', sa.Column('role', sa.String(length=50), nullable=True, server_default='member'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'role')
    op.drop_column('users', 'email_notifications')
    op.drop_column('organizations', 'owner_id')
    op.drop_index(op.f('ix_organization_invites_id'), table_name='organization_invites')
    op.drop_table('organization_invites')