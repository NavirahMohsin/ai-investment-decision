"""add financial news domain tables

Revision ID: 0003_news
Revises: 0002_constraints
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_news"
down_revision = "0002_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider_key", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.String(length=500)),
        sa.Column("feed_url", sa.String(length=500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_key", name="uq_news_sources_provider_key"),
    )
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("news_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(length=255)),
        sa.Column("canonical_url", sa.String(length=1000), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("headline", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("author", sa.String(length=255)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("language", sa.String(length=20)),
        sa.Column("content_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("url_hash", name="uq_news_articles_url_hash"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_news_articles_source_external_id"),
    )
    op.create_index("ix_news_articles_source_id", "news_articles", ["source_id"], unique=False)
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"], unique=False)
    op.create_index("ix_news_articles_source_published_at", "news_articles", ["source_id", "published_at"], unique=False)
    op.create_table(
        "news_article_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_method", sa.String(length=30), nullable=False),
        sa.Column("match_confidence", sa.Numeric(5, 4)),
        sa.Column("matched_text", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("article_id", "company_id", name="uq_news_article_company"),
    )
    op.create_index("ix_news_article_companies_article_id", "news_article_companies", ["article_id"], unique=False)
    op.create_index("ix_news_article_companies_company_id", "news_article_companies", ["company_id"], unique=False)
    op.create_index("ix_news_article_companies_company_article", "news_article_companies", ["company_id", "article_id"], unique=False)
    op.create_table(
        "company_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("alias_type", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "normalized_alias", name="uq_company_alias_normalized"),
    )
    op.create_index("ix_company_aliases_company_id", "company_aliases", ["company_id"], unique=False)
    op.create_index("ix_company_aliases_normalized_alias", "company_aliases", ["normalized_alias"], unique=False)
    op.create_table(
        "news_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("news_sources.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("articles_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("articles_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_news_ingestion_runs_source_id", "news_ingestion_runs", ["source_id"], unique=False)
    op.create_index("ix_news_ingestion_runs_source_started", "news_ingestion_runs", ["source_id", "started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_news_ingestion_runs_source_started", table_name="news_ingestion_runs")
    op.drop_index("ix_news_ingestion_runs_source_id", table_name="news_ingestion_runs")
    op.drop_table("news_ingestion_runs")
    op.drop_index("ix_company_aliases_normalized_alias", table_name="company_aliases")
    op.drop_index("ix_company_aliases_company_id", table_name="company_aliases")
    op.drop_table("company_aliases")
    op.drop_index("ix_news_article_companies_company_article", table_name="news_article_companies")
    op.drop_index("ix_news_article_companies_company_id", table_name="news_article_companies")
    op.drop_index("ix_news_article_companies_article_id", table_name="news_article_companies")
    op.drop_table("news_article_companies")
    op.drop_index("ix_news_articles_source_published_at", table_name="news_articles")
    op.drop_index("ix_news_articles_published_at", table_name="news_articles")
    op.drop_index("ix_news_articles_source_id", table_name="news_articles")
    op.drop_table("news_articles")
    op.drop_table("news_sources")
