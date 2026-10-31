"""record source attribution metadata

Revision ID: 0005_news_source_attribution
Revises: 0004_news_integrity
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_news_source_attribution"
down_revision = "0004_news_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_sources",
        sa.Column("attribution_text", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("news_sources", "attribution_text")
