"""align model constraints

Revision ID: 0002_constraints
Revises: 0001_initial_market_data
"""
from alembic import op

revision = "0002_constraints"
down_revision = "0001_initial_market_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_companies_symbol", table_name="companies")
    with op.batch_alter_table("daily_market_data") as batch_op:
        batch_op.create_foreign_key("fk_market_data_company", "companies", ["company_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("daily_market_data") as batch_op:
        batch_op.drop_constraint("fk_market_data_company", type_="foreignkey")
    op.create_index("ix_companies_symbol", "companies", ["symbol"], unique=False)
