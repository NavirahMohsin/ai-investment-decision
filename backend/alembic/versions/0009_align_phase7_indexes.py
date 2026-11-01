"""Align indexes declared by the SQLAlchemy models.

Revision ID: 0009_align_phase7_indexes
Revises: 0008_company_fundamentals
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0009_align_phase7_indexes"
down_revision: Union[str, None] = "0008_company_fundamentals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_fundamental_data_update_runs_started_at",
        table_name="fundamental_data_update_runs",
    )
    op.drop_index(
        "ix_market_data_update_runs_started_at",
        table_name="market_data_update_runs",
    )
    op.create_index(
        "ix_market_snapshots_company_id",
        "market_snapshots",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_snapshots_company_id", table_name="market_snapshots")
    op.create_index(
        "ix_market_data_update_runs_started_at",
        "market_data_update_runs",
        ["started_at"],
    )
    op.create_index(
        "ix_fundamental_data_update_runs_started_at",
        "fundamental_data_update_runs",
        ["started_at"],
    )
