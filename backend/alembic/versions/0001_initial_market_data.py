"""initial market data schema

Revision ID: 0001_initial_market_data
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_market_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("provider_symbol", sa.String(length=60), nullable=False),
        sa.Column("exchange", sa.String(length=20), nullable=False),
        sa.Column("sector", sa.String(length=120)),
        sa.Column("instrument_type", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("symbol"),
        sa.UniqueConstraint("provider_symbol"),
    )
    op.create_table(
        "daily_market_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=False),
        sa.Column("high", sa.Numeric(18, 6), nullable=False),
        sa.Column("low", sa.Numeric(18, 6), nullable=False),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(18, 6)),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("dividends", sa.Numeric(18, 6)),
        sa.Column("stock_splits", sa.Numeric(18, 6)),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company_id", "trading_date", "provider", name="uq_market_data_company_date_provider"),
    )
    op.create_index("ix_daily_market_data_company_id", "daily_market_data", ["company_id"], unique=False)
    op.create_index("ix_market_data_company_date", "daily_market_data", ["company_id", "trading_date"], unique=False)
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("instrument_symbol", sa.String(length=60), nullable=False),
        sa.Column("requested_start_date", sa.Date(), nullable=False),
        sa.Column("requested_end_date", sa.Date(), nullable=False),
        sa.Column("records_downloaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
    )
    op.create_index("ix_ingestion_runs_instrument_symbol", "ingestion_runs", ["instrument_symbol"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_instrument_symbol", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_index("ix_market_data_company_date", table_name="daily_market_data")
    op.drop_index("ix_daily_market_data_company_id", table_name="daily_market_data")
    op.drop_table("daily_market_data")
    op.drop_table("companies")
