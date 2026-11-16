"""Add research_reports and backtest_runs tables

Revision ID: 0012_research_reports
Revises: 0d911ac2d3e1
Create Date: 2026-11-17 01:50:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0012_research_reports'
down_revision: Union[str, None] = '0d911ac2d3e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Create research_reports table ###
    op.create_table(
        'research_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.String(length=100), nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('report_type', sa.String(length=50), nullable=False, server_default='comprehensive'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('structured_sections', sa.JSON(), nullable=True),
        sa.Column('sources', sa.JSON(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_id', name='uq_research_reports_report_id')
    )
    op.create_index('ix_research_reports_report_id', 'research_reports', ['report_id'], unique=True)
    op.create_index('ix_research_reports_ticker', 'research_reports', ['ticker'], unique=False)
    op.create_index('ix_research_reports_ticker_created', 'research_reports', ['ticker', 'created_at'], unique=False)
    op.create_index('ix_research_reports_report_type', 'research_reports', ['report_type'], unique=False)

    # ### Create backtest_runs table ###
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('backtest_id', sa.String(length=100), nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=100), nullable=True),
        sa.Column('strategy_name', sa.String(length=100), nullable=False, server_default='ML_Strategy'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('initial_capital', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('final_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('total_return', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('annual_return', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('max_drawdown', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('sharpe_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('win_rate', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('profit_factor', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('num_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('equity_curve', sa.JSON(), nullable=True),
        sa.Column('trades', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('backtest_id', name='uq_backtest_runs_backtest_id')
    )
    op.create_index('ix_backtest_runs_backtest_id', 'backtest_runs', ['backtest_id'], unique=True)
    op.create_index('ix_backtest_runs_ticker', 'backtest_runs', ['ticker'], unique=False)
    op.create_index('ix_backtest_runs_ticker_created', 'backtest_runs', ['ticker', 'created_at'], unique=False)
    op.create_index('ix_backtest_runs_strategy', 'backtest_runs', ['strategy_name'], unique=False)


def downgrade() -> None:
    op.drop_table('backtest_runs')
    op.drop_table('research_reports')
