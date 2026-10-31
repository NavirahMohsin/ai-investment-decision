from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.orm import Session

from app.db.models import Company, MarketSnapshot as MarketSnapshotModel
from app.services.calendar import MarketSession, get_market_session
from app.services.providers.base import MarketQuote


class Freshness(StrEnum):
    FRESH = "FRESH"
    DELAYED = "DELAYED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


def classify_freshness(
    market_timestamp: datetime | None,
    retrieved_at: datetime | None = None,
) -> Freshness:
    if market_timestamp is None:
        return Freshness.UNAVAILABLE
    retrieved = retrieved_at or datetime.now(timezone.utc)
    timestamp = market_timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age_seconds = max(0.0, (retrieved - timestamp.astimezone(timezone.utc)).total_seconds())
    if age_seconds <= 5 * 60:
        return Freshness.FRESH
    if age_seconds <= 30 * 60:
        return Freshness.DELAYED
    return Freshness.STALE


def market_session(at: datetime | None = None) -> MarketSession:
    """Get current market session status using exchange calendar."""
    return get_market_session(at)


def quote_response_fields(quote: MarketQuote) -> dict[str, object]:
    price = quote["price"]
    previous = quote["previous_close"]
    absolute = price - previous if price is not None and previous is not None else None
    percentage = (
        absolute / previous * Decimal("100")
        if absolute is not None and previous not in (None, Decimal("0"))
        else None
    )
    return {
        **quote,
        "absolute_change": absolute,
        "percentage_change": percentage,
        "freshness": classify_freshness(
            quote["market_timestamp"], quote["retrieved_at"]
        ),
    }



def store_market_snapshot(
    db: Session,
    company: Company,
    quote: MarketQuote,
    freshness: Freshness,
) -> MarketSnapshotModel:
    """Store a market snapshot in the database."""
    
    price = quote["price"]
    previous = quote["previous_close"]
    absolute = price - previous if price is not None and previous is not None else None
    percentage = (
        absolute / previous * Decimal("100")
        if absolute is not None and previous not in (None, Decimal("0"))
        else None
    )
    
    snapshot = MarketSnapshotModel(
        company_id=company.id,
        price=price or Decimal("0"),
        previous_close=previous,
        open=quote["open"],
        high=quote["day_high"],
        low=quote["day_low"],
        volume=quote["volume"],
        absolute_change=absolute,
        percentage_change=percentage,
        market_timestamp=quote["market_timestamp"],
        retrieved_at=quote["retrieved_at"],
        freshness=freshness.value,
        provider=quote["provider"],
    )
    
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_market_movers(db: Session, limit: int = 10) -> dict[str, list[dict]]:
    """Identify top gainers, losers, and most active by volume."""
    from sqlalchemy import desc, select
    from app.db.models import DailyMarketData
    
    # Get latest two trading dates for each company
    subquery = (
        select(
            DailyMarketData.company_id,
            DailyMarketData.trading_date,
            DailyMarketData.close,
            DailyMarketData.volume,
        )
        .order_by(
            DailyMarketData.company_id,
            desc(DailyMarketData.trading_date),
        )
    )
    
    rows = list(db.execute(subquery).all())
    
    # Group by company
    company_data: dict[int, list] = {}
    for row in rows:
        if row.company_id not in company_data:
            company_data[row.company_id] = []
        company_data[row.company_id].append(row)
    
    # Calculate changes
    movers = []
    for company_id, data in company_data.items():
        if len(data) < 2:
            continue
        
        latest, previous = data[0], data[1]
        if not latest.close or not previous.close or previous.close == 0:
            continue
        
        change_pct = (latest.close - previous.close) / previous.close * Decimal("100")
        
        company = db.get(Company, company_id)
        if company and company.is_active:
            movers.append({
                "symbol": company.symbol,
                "name": company.name,
                "close": float(latest.close),
                "change_pct": float(change_pct),
                "volume": latest.volume,
                "trading_date": latest.trading_date.isoformat(),
            })
    
    # Sort and filter
    movers_sorted = sorted(movers, key=lambda x: x["change_pct"], reverse=True)
    gainers = [m for m in movers_sorted if m["change_pct"] > 0][:limit]
    losers = sorted([m for m in movers_sorted if m["change_pct"] < 0], key=lambda x: x["change_pct"])[:limit]
    most_active = sorted(movers, key=lambda x: x["volume"], reverse=True)[:limit]
    
    return {
        "gainers": gainers,
        "losers": losers,
        "most_active": most_active,
    }
