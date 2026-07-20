"""add_audit_logs_and_user_error_count

Revision ID: 63e7215f6f2f
Revises: cd5cb41a6eca
Create Date: 2026-07-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = '63e7215f6f2f'
down_revision = 'cd5cb41a6eca' 
branch_labels = None
depends_on = None


def upgrade():
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('details', JSON, nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    
    # Add total_errors_ingested to users with default 0
    op.add_column(
        'users',
        sa.Column('total_errors_ingested', sa.Integer(), server_default='0', nullable=False)
    )


def downgrade():
    op.drop_column('users', 'total_errors_ingested')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')