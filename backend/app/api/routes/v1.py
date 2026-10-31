from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
import re
from threading import Lock
from typing import Literal
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Company,
    DailyMarketData,
    IngestionRun,
    NewsArticle,
    NewsArticleCompany,
    NewsIngestionRun,
    NewsSource,
)
from app.db.session import get_db
from app.schemas.market import (
    CompanyResponse,
    HistoricalPriceResponse,
    IndicatorParametersResponse,
    IngestionRunResponse,
    MarketOverviewResponse,
    MarketHealthResponse,
    MarketPricesResponse,
    MarketQuoteResponse,
    MarketRefreshResponse,
    MarketSnapshot,
    TechnicalIndicatorsResponse,
)
from app.schemas.news import (
    NewsArticleDetailRead,
    NewsArticleListItem,
    NewsCompanyMatchRead,
    NewsIngestionRunReadSafe,
    NewsSourceReadSafe,
    PaginatedNewsArticles,
    PaginatedNewsIngestionRuns,
    PaginationMetadata,
    NewsIngestionTriggerResponse,
)
from app.services.indicators import (
    AdjustedCloseUnavailable,
    IndicatorParameters,
    calculate_indicators,
)
from app.services.market_data import (
    Freshness,
    get_market_movers,
    market_session,
    quote_response_fields,
    store_market_snapshot,
)
from app.services.signals import TechnicalSignal, TrendAnalysis, classify_trend, generate_signals
from app.services.news.http_client import SafeFeedHttpClient
from app.services.news.ingestion import ingest_news_source
from app.services.news.source_registry import (
    ContentPolicyStatus,
    get_source,
)
from app.services.providers.yahoo import YahooFinanceProvider
from app.services.refresh import refresh_market_data

router = APIRouter(prefix="/api/v1")
_news_ingestion_locks: dict[str, Lock] = {}
_news_ingestion_locks_guard = Lock()


def _source_ingestion_lock(source_key: str) -> Lock:
    with _news_ingestion_locks_guard:
        return _news_ingestion_locks.setdefault(source_key, Lock())


def _pagination(page: int, page_size: int, total: int) -> PaginationMetadata:
    return PaginationMetadata(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total else 0,
    )


def _validate_news_dates(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")


def _apply_publication_dates(query, start_date: date | None, end_date: date | None):
    if start_date:
        query = query.where(
            NewsArticle.published_at
            >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        query = query.where(
            NewsArticle.published_at
            < datetime.combine(
                end_date + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
        )
    return query


def _article_ordering(query):
    return query.order_by(
        NewsArticle.published_at.is_(None),
        desc(NewsArticle.published_at),
        desc(NewsArticle.id),
    )


def _safe_news_error(value: str | None) -> str | None:
    if not value:
        return None
    if "\n" in value or "\r" in value or "Traceback" in value:
        return "Ingestion failed"
    return re.sub(r"https?://\S+", "[redacted-url]", value)[:500]


def _company_matches(db: Session, article_ids: list[int]) -> dict[int, list[NewsCompanyMatchRead]]:
    if not article_ids:
        return {}
    rows = db.execute(
        select(
            NewsArticleCompany.article_id,
            Company.id,
            Company.symbol,
            Company.name,
            NewsArticleCompany.match_method,
            NewsArticleCompany.match_confidence,
            NewsArticleCompany.matched_text,
        )
        .join(Company, Company.id == NewsArticleCompany.company_id)
        .where(NewsArticleCompany.article_id.in_(article_ids))
        .order_by(NewsArticleCompany.article_id, Company.id)
    ).all()
    matches: dict[int, list[NewsCompanyMatchRead]] = {}
    for row in rows:
        matches.setdefault(row.article_id, []).append(
            NewsCompanyMatchRead(
                company_id=row.id,
                symbol=row.symbol,
                name=row.name,
                match_method=row.match_method,
                match_confidence=row.match_confidence,
                matched_text=row.matched_text,
            )
        )
    return matches


def _article_items(
    db: Session,
    rows: list[tuple[NewsArticle, NewsSource]],
) -> list[NewsArticleListItem]:
    matches = _company_matches(db, [article.id for article, _ in rows])
    return [
        NewsArticleListItem(
            id=article.id,
            source_id=article.source_id,
            source_provider_key=source.provider_key,
            source_name=source.name,
            external_id=article.external_id,
            canonical_url=article.canonical_url,
            headline=article.headline,
            summary=article.summary,
            author=article.author,
            published_at=article.published_at,
            discovered_at=article.discovered_at,
            language=article.language,
            companies=matches.get(article.id, []),
        )
        for article, source in rows
    ]


@router.get("/news", response_model=PaginatedNewsArticles)
def news_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company: str | None = None,
    source: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    _validate_news_dates(start_date, end_date)
    filters = []
    if company:
        filters.append(Company.symbol == company.upper())
    if source:
        filters.append(NewsSource.provider_key == source)
    if search and search.strip():
        filters.append(NewsArticle.headline.ilike(f"%{search.strip()}%"))
    query = (
        select(NewsArticle, NewsSource)
        .join(NewsSource, NewsSource.id == NewsArticle.source_id)
        .where(*filters)
    )
    query = _apply_publication_dates(query, start_date, end_date)
    if company:
        query = query.join(
            NewsArticleCompany,
            NewsArticleCompany.article_id == NewsArticle.id,
        ).join(Company, Company.id == NewsArticleCompany.company_id)
    total_query = select(func.count(func.distinct(NewsArticle.id))).select_from(
        NewsArticle
    ).join(NewsSource, NewsSource.id == NewsArticle.source_id)
    if company:
        total_query = total_query.join(
            NewsArticleCompany,
            NewsArticleCompany.article_id == NewsArticle.id,
        ).join(Company, Company.id == NewsArticleCompany.company_id)
    total_query = total_query.where(*filters)
    total_query = _apply_publication_dates(total_query, start_date, end_date)
    total = db.scalar(total_query) or 0
    query = _article_ordering(query).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(query).unique().all()
    items = _article_items(db, [(row[0], row[1]) for row in rows])
    return PaginatedNewsArticles(
        items=items,
        pagination=_pagination(page, page_size, total),
    )


@router.get("/news/sources", response_model=list[NewsSourceReadSafe])
def news_sources(db: Session = Depends(get_db)):
    sources = db.scalars(
        select(NewsSource).order_by(NewsSource.name, NewsSource.id)
    ).all()
    return [
        NewsSourceReadSafe(
            id=source.id,
            name=source.name,
            provider_key=source.provider_key,
            source_type=source.source_type,
            is_active=source.is_active,
            last_success_at=source.last_success_at,
            last_error=_safe_news_error(source.last_error),
        )
        for source in sources
    ]


@router.get("/news/ingestion/runs", response_model=PaginatedNewsIngestionRuns)
def news_ingestion_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(NewsIngestionRun, NewsSource).outerjoin(
        NewsSource, NewsSource.id == NewsIngestionRun.source_id
    )
    if source:
        query = query.where(NewsSource.provider_key == source)
    if status:
        allowed_statuses = {"running", "success", "partial_success", "failed"}
        if status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Invalid ingestion status")
        query = query.where(NewsIngestionRun.status == status)
    total_query = select(func.count(NewsIngestionRun.id)).select_from(
        NewsIngestionRun
    ).outerjoin(NewsSource, NewsSource.id == NewsIngestionRun.source_id)
    if source:
        total_query = total_query.where(NewsSource.provider_key == source)
    if status:
        total_query = total_query.where(NewsIngestionRun.status == status)
    total = db.scalar(total_query) or 0
    rows = db.execute(
        query.order_by(
            desc(NewsIngestionRun.started_at),
            desc(NewsIngestionRun.id),
        ).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PaginatedNewsIngestionRuns(
        items=[
            NewsIngestionRunReadSafe(
                id=run.id,
                source_id=run.source_id,
                source_provider_key=source.provider_key if source else None,
                source_name=source.name if source else None,
                started_at=run.started_at,
                completed_at=run.completed_at,
                status=run.status,
                articles_discovered=run.articles_discovered,
                articles_inserted=run.articles_inserted,
                articles_skipped=run.articles_skipped,
                error_message=_safe_news_error(run.error_message),
            )
            for run, source in rows
        ],
        pagination=_pagination(page, page_size, total),
    )


@router.post(
    "/news/ingestion/{source_key}",
    response_model=NewsIngestionTriggerResponse,
)
def trigger_news_ingestion(
    source_key: str,
    db: Session = Depends(get_db),
):
    source_config = get_source(source_key)
    if source_config is None:
        raise HTTPException(status_code=404, detail="Unknown news source")
    if not source_config.is_enabled:
        raise HTTPException(status_code=409, detail="News source is disabled")
    if source_config.content_policy_status not in {
        ContentPolicyStatus.APPROVED_CONTENT_STORAGE,
        ContentPolicyStatus.APPROVED_METADATA_ONLY,
    }:
        raise HTTPException(
            status_code=409,
            detail="News source content policy does not approve article storage",
        )
    source = db.scalar(
        select(NewsSource).where(NewsSource.provider_key == source_key)
    )
    if source is None:
        raise HTTPException(
            status_code=409,
            detail="News source is not registered in the database",
        )
    if not source.is_active:
        raise HTTPException(status_code=409, detail="News source is inactive")

    lock = _source_ingestion_lock(source_key)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="News ingestion is already running")
    try:
        if source_config.content_policy_status == ContentPolicyStatus.APPROVED_METADATA_ONLY:
            result = ingest_news_source(
                db,
                source_config,
                SafeFeedHttpClient(),
                allow_metadata_only=True,
            )
        else:
            result = ingest_news_source(
                db,
                source_config,
                SafeFeedHttpClient(),
            )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="News ingestion failed",
        ) from error
    finally:
        lock.release()

    run = db.get(NewsIngestionRun, result.run_id)
    if run is None:
        raise HTTPException(status_code=500, detail="News ingestion result unavailable")
    if result.status == "failed":
        message = "News ingestion completed with failures"
    elif result.status == "partial_success":
        message = "News ingestion completed with skipped articles"
    else:
        message = "News ingestion completed successfully"
    return NewsIngestionTriggerResponse(
        run_id=result.run_id,
        source_key=result.provider_key,
        source_name=source_config.name,
        status=result.status,
        discovered_count=result.articles_discovered,
        inserted_count=result.articles_inserted,
        skipped_count=result.articles_skipped,
        failed_count=0,
        started_at=run.started_at,
        completed_at=run.completed_at,
        message=message,
    )


@router.get("/news/{article_id}", response_model=NewsArticleDetailRead)
def news_article_detail(article_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(NewsArticle, NewsSource)
        .join(NewsSource, NewsSource.id == NewsArticle.source_id)
        .where(NewsArticle.id == article_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="News article not found")
    article, source = row
    item = _article_items(db, [(article, source)])[0]
    return NewsArticleDetailRead(
        **item.model_dump(),
        url_hash=article.url_hash,
        content_hash=article.content_hash,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


@router.get("/companies/{symbol}/news", response_model=PaginatedNewsArticles)
def company_news(
    symbol: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    _validate_news_dates(start_date, end_date)
    company = db.scalar(
        select(Company).where(
            Company.symbol == symbol.upper(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Unknown or inactive company")
    base = (
        select(NewsArticle, NewsSource)
        .join(
            NewsArticleCompany,
            NewsArticleCompany.article_id == NewsArticle.id,
        )
        .join(NewsSource, NewsSource.id == NewsArticle.source_id)
        .where(NewsArticleCompany.company_id == company.id)
    )
    base = _apply_publication_dates(base, start_date, end_date)
    total_query = (
        select(func.count(func.distinct(NewsArticle.id)))
        .select_from(NewsArticle)
        .join(
            NewsArticleCompany,
            NewsArticleCompany.article_id == NewsArticle.id,
        )
        .where(NewsArticleCompany.company_id == company.id)
    )
    total_query = _apply_publication_dates(total_query, start_date, end_date)
    total = db.scalar(total_query) or 0
    rows = db.execute(
        _article_ordering(base)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return PaginatedNewsArticles(
        items=_article_items(db, [(row[0], row[1]) for row in rows]),
        pagination=_pagination(page, page_size, total),
    )


@router.get("/companies", response_model=list[CompanyResponse])
def companies(exchange: str | None = None, instrument_type: str | None = None, db: Session = Depends(get_db)):
    query = select(Company).where(Company.is_active.is_(True)).order_by(Company.name)
    if exchange:
        query = query.where(Company.exchange == exchange.upper())
    if instrument_type:
        query = query.where(Company.instrument_type == instrument_type.lower())
    return list(db.scalars(query))


def snapshot(db: Session, company: Company) -> MarketSnapshot:
    rows = list(db.scalars(select(DailyMarketData).where(DailyMarketData.company_id == company.id).order_by(desc(DailyMarketData.trading_date)).limit(2)))
    if not rows:
        return MarketSnapshot(symbol=company.symbol, available=False)
    latest, previous = rows[0], rows[1] if len(rows) > 1 else None
    absolute = latest.close - previous.close if previous else None
    percentage = (
        (absolute / previous.close * Decimal("100")).quantize(Decimal("0.000001"))
        if previous and previous.close
        else None
    )
    return MarketSnapshot(symbol=company.symbol, available=True, trading_date=latest.trading_date, latest_close=latest.close, previous_close=previous.close if previous else None, absolute_change=absolute, percentage_change=percentage, provider=latest.provider)


@router.get("/market/overview", response_model=MarketOverviewResponse)
def market_overview(db: Session = Depends(get_db)):
    instruments = []
    for symbol in ("NIFTY50", "SENSEX"):
        company = db.scalar(select(Company).where(Company.symbol == symbol, Company.is_active.is_(True)))
        if company:
            instruments.append(snapshot(db, company))
        else:
            instruments.append(MarketSnapshot(symbol=symbol, available=False))
    return MarketOverviewResponse(
        instruments=instruments,
        market_status=market_session().value,
        retrieved_at=datetime.now(timezone.utc),
    )


def _quote_for_company(company: Company) -> MarketQuoteResponse:
    try:
        fields = quote_response_fields(
            YahooFinanceProvider().quote(company.provider_symbol)
        )
    except Exception:
        return MarketQuoteResponse(
            symbol=company.symbol,
            provider_symbol=company.provider_symbol,
            exchange=company.exchange,
            instrument_type=company.instrument_type,
            freshness=Freshness.UNAVAILABLE.value,
            provider=YahooFinanceProvider.name,
        )
    return MarketQuoteResponse(
        symbol=company.symbol,
        provider_symbol=company.provider_symbol,
        exchange=company.exchange,
        instrument_type=company.instrument_type,
        **fields,
    )


@router.get("/market/quotes/{symbol}", response_model=MarketQuoteResponse)
def market_quote(symbol: str, db: Session = Depends(get_db)):
    company = db.scalar(
        select(Company).where(
            Company.symbol == symbol.upper(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {symbol}")
    return _quote_for_company(company)


@router.get("/market/prices", response_model=MarketPricesResponse)
def market_prices(
    symbol: str | None = None,
    exchange: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(Company).where(Company.is_active.is_(True)).order_by(Company.symbol)
    if symbol:
        query = query.where(Company.symbol == symbol.upper())
    if exchange:
        query = query.where(Company.exchange == exchange.upper())
    companies_to_quote = list(db.scalars(query))
    if symbol and not companies_to_quote:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {symbol}")
    return MarketPricesResponse(
        items=[_quote_for_company(company) for company in companies_to_quote],
        retrieved_at=datetime.now(timezone.utc),
    )


@router.get("/market/health", response_model=MarketHealthResponse)
def market_health(db: Session = Depends(get_db)):
    companies_to_check = list(
        db.scalars(select(Company).where(Company.is_active.is_(True)))
    )
    unavailable: list[str] = []
    available = 0
    for company in companies_to_check:
        if _quote_for_company(company).freshness == Freshness.UNAVAILABLE.value:
            unavailable.append(company.symbol)
        else:
            available += 1
    return MarketHealthResponse(
        provider=YahooFinanceProvider.name,
        status="healthy" if available else "unavailable",
        market_status=market_session().value,
        checked_at=datetime.now(timezone.utc),
        available_instruments=available,
        unavailable_instruments=unavailable,
    )


@router.post("/market/refresh", response_model=MarketRefreshResponse)
def market_refresh(symbol: str | None = None, db: Session = Depends(get_db)):
    started_at = datetime.now(timezone.utc)
    result = refresh_market_data(db, symbol.upper() if symbol else None)
    completed_at = datetime.now(timezone.utc)
    if result["status"] == "already_running":
        raise HTTPException(status_code=409, detail="Market refresh is already running")
    return MarketRefreshResponse(
        **result,
        provider=YahooFinanceProvider.name,
        started_at=started_at,
        completed_at=completed_at,
        message="Market history refresh completed",
    )


@router.get("/stocks/{symbol}/history", response_model=HistoricalPriceResponse)
def stock_history(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    interval: str = Query("1d"),
    db: Session = Depends(get_db),
):
    if interval not in {"1d", "1wk", "1mo"}:
        raise HTTPException(status_code=400, detail="interval must be one of 1d, 1wk, or 1mo")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    company = db.scalar(select(Company).where(Company.symbol == symbol.upper(), Company.is_active.is_(True)))
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {symbol}")
    query = select(DailyMarketData).where(DailyMarketData.company_id == company.id).order_by(DailyMarketData.trading_date)
    if start_date:
        query = query.where(DailyMarketData.trading_date >= start_date)
    if end_date:
        query = query.where(DailyMarketData.trading_date <= end_date)
    records = list(db.scalars(query))
    if interval != "1d":
        grouped: dict[date, list[DailyMarketData]] = {}
        for record in records:
            bucket = (
                record.trading_date - timedelta(days=record.trading_date.weekday())
                if interval == "1wk"
                else record.trading_date.replace(day=1)
            )
            grouped.setdefault(bucket, []).append(record)
        records = [
            DailyMarketData(
                trading_date=bucket,
                open=values[0].open,
                high=max(item.high for item in values),
                low=min(item.low for item in values),
                close=values[-1].close,
                adjusted_close=values[-1].adjusted_close,
                volume=sum(item.volume for item in values),
                dividends=sum((item.dividends or Decimal("0") for item in values), Decimal("0")),
                stock_splits=values[-1].stock_splits,
                provider=values[-1].provider,
            )
            for bucket, values in sorted(grouped.items())
        ]
    return HistoricalPriceResponse(symbol=company.symbol, provider_symbol=company.provider_symbol, instrument_type=company.instrument_type, exchange=company.exchange, source="Yahoo Finance", records=records)


@router.get("/stocks/{symbol}/indicators", response_model=TechnicalIndicatorsResponse)
def stock_indicators(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    price_field: Literal["close", "adjusted_close"] = Query("close"),
    sma_period: int = Query(20, ge=1, le=2000),
    ema_period: int = Query(20, ge=1, le=2000),
    rsi_period: int = Query(14, ge=1, le=2000),
    macd_fast_period: int = Query(12, ge=1, le=2000),
    macd_slow_period: int = Query(26, ge=1, le=2000),
    macd_signal_period: int = Query(9, ge=1, le=2000),
    bollinger_period: int = Query(20, ge=1, le=2000),
    bollinger_std_dev: float = Query(2.0, gt=0),
    atr_period: int = Query(14, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    if macd_fast_period >= macd_slow_period:
        raise HTTPException(status_code=400, detail="macd_fast_period must be smaller than macd_slow_period")
    if not isfinite(bollinger_std_dev):
        raise HTTPException(status_code=400, detail="bollinger_std_dev must be finite and greater than zero")

    company = db.scalar(select(Company).where(Company.symbol == symbol.upper(), Company.is_active.is_(True)))
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {symbol}")

    query = select(DailyMarketData).where(DailyMarketData.company_id == company.id)
    if end_date:
        query = query.where(DailyMarketData.trading_date <= end_date)
    rows = list(db.scalars(query.order_by(DailyMarketData.trading_date)))
    parameters = IndicatorParameters(
        price_field=price_field,
        sma_period=sma_period,
        ema_period=ema_period,
        rsi_period=rsi_period,
        macd_fast_period=macd_fast_period,
        macd_slow_period=macd_slow_period,
        macd_signal_period=macd_signal_period,
        bollinger_period=bollinger_period,
        bollinger_std_dev=bollinger_std_dev,
        atr_period=atr_period,
    )
    try:
        records, available_records, actual_first_date, actual_last_date = calculate_indicators(
            rows, parameters, start_date, end_date
        )
    except AdjustedCloseUnavailable as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    providers = {row.provider for row in rows}
    provider = next(iter(providers)) if len(providers) == 1 else None
    return TechnicalIndicatorsResponse(
        symbol=company.symbol,
        provider_symbol=company.provider_symbol,
        exchange=company.exchange,
        instrument_type=company.instrument_type,
        source="Yahoo Finance" if provider == "yahoo_finance" else provider,
        provider=provider,
        price_field=price_field,
        requested_start_date=start_date,
        requested_end_date=end_date,
        actual_first_date=actual_first_date,
        actual_last_date=actual_last_date,
        available_records=available_records,
        returned_records=len(records),
        parameters=IndicatorParametersResponse(**parameters.__dict__),
        calculation_metadata={
            "ema": "pandas ewm(span=period, adjust=False); values are null until the full period is available",
            "rsi": "Wilder-style exponential smoothing; flat periods return 0 and zero-loss rising periods return 100",
            "bollinger_bands": "Population standard deviation (ddof=0)",
            "atr": "Wilder smoothing of true range; the first true range uses high-low because no previous close exists",
            "adjusted_close_atr": "ATR always uses stored raw high, low, and previous raw close; adjusted-close ATR is not fully split-adjusted",
        },
        records=records,
    )


@router.get("/market/movers")
def market_movers(limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Get top gainers, losers, and most active stocks."""
    return get_market_movers(db, limit)


@router.get("/stocks/{symbol}/signals")
def stock_signals(symbol: str, db: Session = Depends(get_db)):
    """Generate technical signals for a stock."""
    company = db.scalar(
        select(Company).where(
            Company.symbol == symbol.upper(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {symbol}")
    
    # Get historical data
    rows = list(
        db.scalars(
            select(DailyMarketData)
            .where(DailyMarketData.company_id == company.id)
            .order_by(DailyMarketData.trading_date)
        )
    )
    
    if len(rows) < 2:
        return {
            "symbol": company.symbol,
            "signals": [],
            "trend": None,
            "message": "Insufficient historical data for signal generation",
        }
    
    parameters = IndicatorParameters()
    signals = generate_signals(rows, parameters)
    
    # Get trend classification
    records, _, _, _ = calculate_indicators(rows, parameters)
    trend = None
    if records:
        latest = records[-1]
        if latest["close"] is not None:
            trend_analysis = classify_trend(
                current_price=latest["close"],
                ema=latest["ema"],
                rsi=latest["rsi"],
                adx=latest["adx"],
                macd_histogram=latest["macd_histogram"],
            )
            trend = {
                "classification": trend_analysis.classification,
                "explanation": trend_analysis.explanation,
                "current_price": trend_analysis.current_price,
                "ema": trend_analysis.ema_value,
                "rsi": trend_analysis.rsi_value,
                "adx": trend_analysis.adx_value,
                "macd_histogram": trend_analysis.macd_histogram,
            }
    
    return {
        "symbol": company.symbol,
        "provider_symbol": company.provider_symbol,
        "exchange": company.exchange,
        "signals": [
            {
                "signal_type": signal.signal_type,
                "timestamp": signal.timestamp.isoformat(),
                "price": signal.price,
                "explanation": signal.explanation,
                "indicator_values": signal.indicator_values,
                "strength": signal.strength,
            }
            for signal in signals
        ],
        "trend": trend,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ingestion/runs", response_model=list[IngestionRunResponse])
def ingestion_runs(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return list(db.scalars(select(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(limit)))


@router.get("/market/snapshots/{symbol}")
def market_snapshots(
    symbol: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get historical market snapshots for a symbol."""
    from app.db.models import MarketSnapshot
    from app.schemas.market import MarketSnapshotsResponse, MarketSnapshotRecord
    
    company = db.scalar(
        select(Company).where(
            Company.symbol == symbol.upper(),
            Company.is_active.is_(True),
        )
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {symbol}")
    
    snapshots = list(
        db.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.company_id == company.id)
            .order_by(desc(MarketSnapshot.retrieved_at))
            .limit(limit)
        )
    )
    
    total = db.scalar(
        select(func.count(MarketSnapshot.id))
        .where(MarketSnapshot.company_id == company.id)
    ) or 0
    
    return MarketSnapshotsResponse(
        symbol=company.symbol,
        snapshots=[MarketSnapshotRecord.model_validate(s) for s in snapshots],
        total_count=total,
    )


@router.get("/market/update-runs")
def market_update_runs(
    run_type: str | None = Query(None, pattern="^(quotes|historical)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get market data update run history."""
    from app.db.models import MarketDataUpdateRun
    from app.schemas.market import MarketDataUpdateRunsResponse, MarketDataUpdateRunRecord
    
    query = select(MarketDataUpdateRun).order_by(desc(MarketDataUpdateRun.started_at))
    
    if run_type:
        query = query.where(MarketDataUpdateRun.run_type == run_type)
    
    runs = list(db.scalars(query.limit(limit)))
    
    total_query = select(func.count(MarketDataUpdateRun.id))
    if run_type:
        total_query = total_query.where(MarketDataUpdateRun.run_type == run_type)
    
    total = db.scalar(total_query) or 0
    
    return MarketDataUpdateRunsResponse(
        runs=[MarketDataUpdateRunRecord.model_validate(r) for r in runs],
        total_count=total,
    )
