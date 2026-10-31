from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_HISTORY_YEARS
from app.db.models import Company, DailyMarketData
from app.services.ingestion import ingest_instrument
from app.services.market_data import classify_freshness, store_market_snapshot
from app.services.providers.yahoo import YahooFinanceProvider

_refresh_lock = Lock()


def refresh_market_data(db: Session, symbol: str | None = None) -> dict[str, int | str]:
    """Refresh historical market data for all or specific instruments."""
    if not _refresh_lock.acquire(blocking=False):
        return {
            "status": "already_running",
            "instruments_processed": 0,
            "successful_runs": 0,
            "failed_runs": 0,
        }
    try:
        query = select(Company).where(Company.is_active.is_(True)).order_by(Company.symbol)
        if symbol:
            query = query.where(Company.symbol == symbol.upper())
        companies = list(db.scalars(query))
        provider = YahooFinanceProvider()
        successful = 0
        failed = 0
        for company in companies:
            latest = db.scalar(
                select(DailyMarketData.trading_date)
                .where(
                    DailyMarketData.company_id == company.id,
                    DailyMarketData.provider == provider.name,
                )
                .order_by(DailyMarketData.trading_date.desc())
            )
            start = latest + timedelta(days=1) if latest else date.today() - timedelta(days=365 * DEFAULT_HISTORY_YEARS)
            run = ingest_instrument(db, company, provider, start, date.today())
            if run.status in {"success", "empty"}:
                successful += 1
            else:
                failed += 1
        return {
            "status": "success" if failed == 0 else "partial_success",
            "instruments_processed": len(companies),
            "successful_runs": successful,
            "failed_runs": failed,
        }
    finally:
        _refresh_lock.release()


def refresh_live_quotes(db: Session, store_snapshots: bool = True) -> dict[str, object]:
    """Refresh live quotes for all active instruments."""
    companies = list(db.scalars(select(Company).where(Company.is_active.is_(True))))
    provider = YahooFinanceProvider()
    
    successful = 0
    failed = 0
    failed_symbols: list[str] = []
    
    for company in companies:
        try:
            quote = provider.quote(company.provider_symbol)
            freshness = classify_freshness(quote["market_timestamp"], quote["retrieved_at"])
            
            if store_snapshots and quote["price"] is not None:
                store_market_snapshot(db, company, quote, freshness)
            
            successful += 1
        except Exception:
            failed += 1
            failed_symbols.append(company.symbol)
    
    return {
        "status": "success" if failed == 0 else "partial_success",
        "successful": successful,
        "failed": failed,
        "failed_symbols": failed_symbols,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
