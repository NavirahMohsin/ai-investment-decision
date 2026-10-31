"""Add market_data_update_runs table

Revision ID: 0007_market_data_update_runs
Revises: 0006_market_snapshots
Create Date: 2024-10-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_market_data_update_runs'
down_revision: Union[str, None] = '0006_market_snapshots'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'market_data_update_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('instruments_processed', sa.Integer(), nullable=False),
        sa.Column('successful_count', sa.Integer(), nullable=False),
        sa.Column('failed_count', sa.Integer(), nullable=False),
        sa.Column('failed_symbols', sa.String(length=500), nullable=True),
        sa.Column('trigger_source', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_market_data_update_runs_started_at', 'market_data_update_runs', ['started_at'])


def downgrade() -> None:
    op.drop_index('ix_market_data_update_runs_started_at', table_name='market_data_update_runs')
    op.drop_table('market_data_update_runs')
