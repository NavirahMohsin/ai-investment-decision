from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, DailyMarketData, IngestionRun
from app.services.providers import MarketDataProvider


class InvalidMarketRow(ValueError):
    pass


def validate_market_row(row: dict) -> None:
    required = ("open", "high", "low", "close", "volume")
    if any(row.get(field) is None for field in required):
        raise InvalidMarketRow("OHLCV fields cannot be missing")
    prices = {field: Decimal(str(row[field])) for field in ("open", "high", "low", "close")}
    if any(value <= 0 for value in prices.values()):
        raise InvalidMarketRow("OHLC prices must be positive")
    if prices["high"] < max(prices["open"], prices["close"], prices["low"]):
        raise InvalidMarketRow("High cannot be below open, close, or low")
    if prices["low"] > min(prices["open"], prices["close"], prices["high"]):
        raise InvalidMarketRow("Low cannot be above open, close, or high")
    if int(row["volume"]) < 0:
        raise InvalidMarketRow("Volume cannot be negative")
    if not isinstance(row["trading_date"], date):
        raise InvalidMarketRow("Trading date must be a date")


def ingest_instrument(
    db: Session,
    company: Company,
    provider: MarketDataProvider,
    start_date: date,
    end_date: date,
) -> IngestionRun:
    run = IngestionRun(
        provider=provider.name,
        instrument_symbol=company.symbol,
        requested_start_date=start_date,
        requested_end_date=end_date,
        status="running",
    )
    db.add(run)
    db.flush()
    try:
        rows = provider.download(company.provider_symbol, start_date, end_date)
        run.records_downloaded = len(rows)
        unique_rows = {row["trading_date"]: row for row in rows}
        existing = {
            record.trading_date: record
            for record in db.scalars(
                select(DailyMarketData).where(
                    DailyMarketData.company_id == company.id,
                    DailyMarketData.provider == provider.name,
                    DailyMarketData.trading_date.between(start_date, end_date),
                )
            )
        }
        for row in unique_rows.values():
            validate_market_row(row)
            record = existing.get(row["trading_date"])
            values = {
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "adjusted_close": row.get("adjusted_close"),
                "volume": row["volume"],
                "dividends": row.get("dividends"),
                "stock_splits": row.get("stock_splits"),
            }
            if record is None:
                db.add(DailyMarketData(company_id=company.id, trading_date=row["trading_date"], provider=provider.name, **values))
                run.records_inserted += 1
            else:
                for key, value in values.items():
                    setattr(record, key, value)
                run.records_updated += 1
        run.status = "empty" if not rows else "success"
    except Exception as error:
        run.status = "failed"
        run.error_message = str(error)
    run.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    return run
