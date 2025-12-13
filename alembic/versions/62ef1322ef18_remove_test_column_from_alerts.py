"""Remove test_column from alerts

Revision ID: 62ef1322ef18
Revises: fb78200f2cf6
Create Date: 2025-09-14 18:09:51.124301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '62ef1322ef18'
down_revision: Union[str, Sequence[str], None] = 'fb78200f2cf6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('alerts', 'test_column')

def downgrade() -> None:
    op.add_column('alerts', sa.Column('test_column', sa.VARCHAR(), autoincrement=False, nullable=True))
