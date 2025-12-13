"""Add test_column to alerts

Revision ID: fb78200f2cf6
Revises: 2a265a20dd6e
Create Date: 2025-09-14 18:03:25.336073

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fb78200f2cf6'
down_revision: Union[str, Sequence[str], None] = '2a265a20dd6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alerts', sa.Column('test_column', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('alerts', 'test_column')

