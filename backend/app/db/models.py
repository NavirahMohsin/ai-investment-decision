from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class Sector(Base):
    __tablename__ = "sectors"
    __table_args__ = (
        UniqueConstraint("sector_name", "industry_name", name="uq_sector_industry"),
        Index("ix_sectors_sector_name", "sector_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector_name: Mapped[str] = mapped_column(String(120), nullable=False)
    industry_name: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="yahoo_finance")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    provider_symbol: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    exchange: Mapped[str] = mapped_column(String(20), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120))
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id", ondelete="SET NULL"), index=True)
    instrument_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyMarketData(Base):
    __tablename__ = "daily_market_data"
    __table_args__ = (
        UniqueConstraint("company_id", "trading_date", "provider", name="uq_market_data_company_date_provider"),
        Index("ix_market_data_company_date", "company_id", "trading_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    dividends: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    stock_splits: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_symbol: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    requested_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    records_downloaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    feed_url: Mapped[str | None] = mapped_column(String(500))
    attribution_text: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_news_articles_url_hash"),
        UniqueConstraint("source_id", "external_id", name="uq_news_articles_source_external_id"),
        Index("ix_news_articles_published_at", "published_at"),
        Index("ix_news_articles_source_published_at", "source_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255))
    canonical_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    language: Mapped[str | None] = mapped_column(String(20))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class NewsArticleCompany(Base):
    __tablename__ = "news_article_companies"
    __table_args__ = (
        UniqueConstraint("article_id", "company_id", name="uq_news_article_company"),
        Index("ix_news_article_companies_company_article", "company_id", "article_id"),
        CheckConstraint(
            "match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)",
            name="ck_news_article_company_match_confidence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    match_method: Mapped[str] = mapped_column(String(30), nullable=False)
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    matched_text: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class CompanyAlias(Base):
    __tablename__ = "company_aliases"
    __table_args__ = (
        UniqueConstraint("company_id", "normalized_alias", name="uq_company_alias_normalized"),
        Index("ix_company_aliases_normalized_alias", "normalized_alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_market_snapshots_company_retrieved", "company_id", "retrieved_at"),
        Index("ix_market_snapshots_retrieved_at", "retrieved_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(Integer)
    absolute_change: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    percentage_change: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    market_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    freshness: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class MarketDataUpdateRun(Base):
    """Track market data update runs."""
    __tablename__ = "market_data_update_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'quotes' or 'historical'
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'running', 'completed', 'partial', 'failed'
    instruments_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_symbols: Mapped[str | None] = mapped_column(String(500))  # Comma-separated
    trigger_source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'scheduled' or 'manual'
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_message: Mapped[str | None] = mapped_column(String(500))


class CompanyFinancial(Base):
    """Store company financial metrics and ratios."""
    __tablename__ = "company_financials"
    __table_args__ = (
        UniqueConstraint("company_id", "metric_name", "period_end", "period_type", name="uq_company_financial"),
        Index("ix_company_financials_company_period", "company_id", "period_end"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    period_end: Mapped[date | None] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'annual', 'quarterly', 'ttm'
    statement_type: Mapped[str | None] = mapped_column(String(20))  # 'income', 'balance', 'cashflow', 'ratio'
    currency: Mapped[str | None] = mapped_column(String(10))
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="yahoo_finance")
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class CompanyFundamentalInfo(Base):
    """Store company information and metadata."""
    __tablename__ = "company_fundamental_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    business_summary: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str | None] = mapped_column(String(10))
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    enterprise_value: Mapped[int | None] = mapped_column(BigInteger)
    employees: Mapped[int | None] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="yahoo_finance")
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class CompanyProfile(Base):
    """Extended profile metadata sourced from Yahoo Finance."""
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(160))
    headquarters_city: Mapped[str | None] = mapped_column(String(120))
    headquarters_state: Mapped[str | None] = mapped_column(String(120))
    headquarters_country: Mapped[str | None] = mapped_column(String(120))
    products_services: Mapped[list[str] | None] = mapped_column(JSON)
    revenue_segments: Mapped[dict[str, float] | None] = mapped_column(JSON)
    full_time_employees: Mapped[int | None] = mapped_column(Integer)
    fiscal_year_end: Mapped[str | None] = mapped_column(String(20))
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, default="yahoo_finance")
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class FundamentalDataUpdateRun(Base):
    """Track fundamental data update runs."""
    __tablename__ = "fundamental_data_update_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'company_info', 'financials', 'ratios', 'all'
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'running', 'completed', 'partial', 'failed'
    companies_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_symbols: Mapped[str | None] = mapped_column(String(500))
    trigger_source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'scheduled' or 'manual'
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_message: Mapped[str | None] = mapped_column(String(500))



class NewsIngestionRun(Base):
    __tablename__ = "news_ingestion_runs"
    __table_args__ = (
        Index("ix_news_ingestion_runs_source_started", "source_id", "started_at"),
        CheckConstraint(
            "status IN ('running', 'success', 'partial_success', 'failed')",
            name="ck_news_ingestion_runs_status",
        ),
        CheckConstraint("articles_discovered >= 0", name="ck_news_ingestion_runs_discovered_nonnegative"),
        CheckConstraint("articles_inserted >= 0", name="ck_news_ingestion_runs_inserted_nonnegative"),
        CheckConstraint("articles_updated >= 0", name="ck_news_ingestion_runs_updated_nonnegative"),
        CheckConstraint("articles_skipped >= 0", name="ck_news_ingestion_runs_skipped_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("news_sources.id", ondelete="SET NULL"), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    articles_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
