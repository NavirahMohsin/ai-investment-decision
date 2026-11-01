"""Add company fundamentals tables

Revision ID: 0008_company_fundamentals
Revises: 0007_market_data_update_runs
Create Date: 2026-10-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_company_fundamentals'
down_revision: Union[str, None] = '0007_market_data_update_runs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create company_financials table
    op.create_table(
        'company_financials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('statement_type', sa.String(length=20), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'metric_name', 'period_end', 'period_type', name='uq_company_financial')
    )
    op.create_index('ix_company_financials_company_id', 'company_financials', ['company_id'])
    op.create_index('ix_company_financials_company_period', 'company_financials', ['company_id', 'period_end'])
    
    # Create company_fundamental_info table
    op.create_table(
        'company_fundamental_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('business_summary', sa.Text(), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('market_cap', sa.BigInteger(), nullable=True),
        sa.Column('enterprise_value', sa.BigInteger(), nullable=True),
        sa.Column('employees', sa.Integer(), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id')
    )
    op.create_index('ix_company_fundamental_info_company_id', 'company_fundamental_info', ['company_id'], unique=True)
    
    # Create fundamental_data_update_runs table
    op.create_table(
        'fundamental_data_update_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('companies_processed', sa.Integer(), nullable=False),
        sa.Column('successful_count', sa.Integer(), nullable=False),
        sa.Column('failed_count', sa.Integer(), nullable=False),
        sa.Column('failed_symbols', sa.String(length=500), nullable=True),
        sa.Column('trigger_source', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_fundamental_data_update_runs_started_at', 'fundamental_data_update_runs', ['started_at'])


def downgrade() -> None:
    op.drop_index('ix_fundamental_data_update_runs_started_at', table_name='fundamental_data_update_runs')
    op.drop_table('fundamental_data_update_runs')
    op.drop_index('ix_company_fundamental_info_company_id', table_name='company_fundamental_info')
    op.drop_table('company_fundamental_info')
    op.drop_index('ix_company_financials_company_period', table_name='company_financials')
    op.drop_index('ix_company_financials_company_id', table_name='company_financials')
    op.drop_table('company_financials')
