"""Add role column to users table

Revision ID: add_user_roles
Revises: add_audit_logs
Create Date: 2025-12-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_roles'
down_revision: Union[str, Sequence[str], None] = 'add_audit_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role column to users table."""
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='analyst', nullable=False))


def downgrade() -> None:
    """Remove role column from users table."""
    op.drop_column('users', 'role')
