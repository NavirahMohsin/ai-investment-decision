"""add news integrity constraints

Revision ID: 0004_news_integrity
Revises: 0003_news
"""
from alembic import op


revision = "0004_news_integrity"
down_revision = "0003_news"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_article_companies") as batch_op:
        batch_op.create_check_constraint(
            "ck_news_article_company_match_confidence",
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
        )
    with op.batch_alter_table("news_ingestion_runs") as batch_op:
        batch_op.create_check_constraint(
            "ck_news_ingestion_runs_status",
            "status IN ('running', 'success', 'partial_success', 'failed')",
        )
        batch_op.create_check_constraint(
            "ck_news_ingestion_runs_discovered_nonnegative",
            "articles_discovered >= 0",
        )
        batch_op.create_check_constraint(
            "ck_news_ingestion_runs_inserted_nonnegative",
            "articles_inserted >= 0",
        )
        batch_op.create_check_constraint(
            "ck_news_ingestion_runs_updated_nonnegative",
            "articles_updated >= 0",
        )
        batch_op.create_check_constraint(
            "ck_news_ingestion_runs_skipped_nonnegative",
            "articles_skipped >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("news_ingestion_runs") as batch_op:
        batch_op.drop_constraint("ck_news_ingestion_runs_skipped_nonnegative", type_="check")
        batch_op.drop_constraint("ck_news_ingestion_runs_updated_nonnegative", type_="check")
        batch_op.drop_constraint("ck_news_ingestion_runs_inserted_nonnegative", type_="check")
        batch_op.drop_constraint("ck_news_ingestion_runs_discovered_nonnegative", type_="check")
        batch_op.drop_constraint("ck_news_ingestion_runs_status", type_="check")
    with op.batch_alter_table("news_article_companies") as batch_op:
        batch_op.drop_constraint("ck_news_article_company_match_confidence", type_="check")
