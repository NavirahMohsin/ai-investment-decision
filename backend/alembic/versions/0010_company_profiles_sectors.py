"""Add company profiles and normalized sector classifications.

Revision ID: 0010_company_profiles_sectors
Revises: 0009_align_phase7_indexes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_company_profiles_sectors"
down_revision: Union[str, None] = "0009_align_phase7_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sector_name", sa.String(length=120), nullable=False),
        sa.Column("industry_name", sa.String(length=160), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(length=50), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sector_name", "industry_name", name="uq_sector_industry"),
    )
    op.create_index("ix_sectors_sector_name", "sectors", ["sector_name"])
    with op.batch_alter_table("companies", recreate="always") as batch:
        batch.add_column(sa.Column("sector_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_companies_sector_id_sectors",
            "sectors",
            ["sector_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_companies_sector_id", "companies", ["sector_id"])
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("industry", sa.String(length=160), nullable=True),
        sa.Column("headquarters_city", sa.String(length=120), nullable=True),
        sa.Column("headquarters_state", sa.String(length=120), nullable=True),
        sa.Column("headquarters_country", sa.String(length=120), nullable=True),
        sa.Column("products_services", sa.JSON(), nullable=True),
        sa.Column("revenue_segments", sa.JSON(), nullable=True),
        sa.Column("full_time_employees", sa.Integer(), nullable=True),
        sa.Column("fiscal_year_end", sa.String(length=20), nullable=True),
        sa.Column("data_source", sa.String(length=50), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_company_profiles_company_id", "company_profiles", ["company_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_company_profiles_company_id", table_name="company_profiles")
    op.drop_table("company_profiles")
    op.drop_index("ix_companies_sector_id", table_name="companies")
    with op.batch_alter_table("companies", recreate="always") as batch:
        batch.drop_constraint("fk_companies_sector_id_sectors", type_="foreignkey")
        batch.drop_column("sector_id")
    op.drop_index("ix_sectors_sector_name", table_name="sectors")
    op.drop_table("sectors")
