"""Add model_metrics table

Revision ID: add_model_metrics
Revises: add_user_roles
Create Date: 2025-12-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_model_metrics'
down_revision: Union[str, Sequence[str], None] = 'add_user_roles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add model_metrics table."""
    op.create_table(
        'model_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('model_type', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=100), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('recall', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_metrics_timestamp'), 'model_metrics', ['timestamp'], unique=False)


def downgrade() -> None:
    """Remove model_metrics table."""
    op.drop_index(op.f('ix_model_metrics_timestamp'), table_name='model_metrics')
    op.drop_table('model_metrics')
