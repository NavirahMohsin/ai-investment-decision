from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Company, DailyMarketData, IngestionRun
from app.db.session import get_db
from app.schemas.market import CompanyResponse, HistoricalPriceResponse, IngestionRunResponse, MarketOverviewResponse, MarketSnapshot

router = APIRouter(prefix="/api/v1")


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
    return MarketOverviewResponse(instruments=instruments)


@router.get("/stocks/{symbol}/history", response_model=HistoricalPriceResponse)
def stock_history(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    interval: str = Query("1d"),
    db: Session = Depends(get_db),
):
    if interval != "1d":
        raise HTTPException(status_code=400, detail="Only daily interval 1d is supported")
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
    return HistoricalPriceResponse(symbol=company.symbol, provider_symbol=company.provider_symbol, instrument_type=company.instrument_type, exchange=company.exchange, source="Yahoo Finance", records=records)


@router.get("/ingestion/runs", response_model=list[IngestionRunResponse])
def ingestion_runs(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return list(db.scalars(select(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(limit)))
