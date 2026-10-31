"""Add market snapshots table

Revision ID: 0006_market_snapshots
Revises: 0005_news_source_attribution
Create Date: 2026-10-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_market_snapshots'
down_revision: Union[str, None] = '0005_news_source_attribution'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'market_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('previous_close', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('open', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('high', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('low', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('absolute_change', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('percentage_change', sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column('market_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('freshness', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_market_snapshots_company_retrieved', 'market_snapshots', ['company_id', 'retrieved_at'])
    op.create_index('ix_market_snapshots_retrieved_at', 'market_snapshots', ['retrieved_at'])


def downgrade() -> None:
    op.drop_index('ix_market_snapshots_retrieved_at')
    op.drop_index('ix_market_snapshots_company_retrieved')
    op.drop_table('market_snapshots')
