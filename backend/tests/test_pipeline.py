from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Company, DailyMarketData
from app.services.ingestion import InvalidMarketRow, ingest_instrument
from app.services.providers.base import MarketDataProvider


class FakeProvider(MarketDataProvider):
    name = "test_provider"

    def __init__(self, rows):
        self.rows = rows

    def download(self, provider_symbol, start_date, end_date):
        return self.rows


def row(close="105"):
    return {
        "trading_date": date(2026, 1, 2),
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("95"),
        "close": Decimal(close),
        "adjusted_close": Decimal(close),
        "volume": 100,
        "dividends": None,
        "stock_splits": None,
    }


def test_invalid_ohlc_is_rejected():
    invalid = row()
    invalid["high"] = Decimal("90")
    with pytest.raises(InvalidMarketRow):
        from app.services.ingestion import validate_market_row
        validate_market_row(invalid)


def test_ingestion_is_idempotent(db_session):
    company = Company(name="Example", symbol="EXAMPLE", provider_symbol="EXAMPLE.NS", exchange="NSE", instrument_type="company")
    db_session.add(company)
    db_session.commit()
    provider = FakeProvider([row()])
    first = ingest_instrument(db_session, company, provider, date(2026, 1, 1), date(2026, 1, 3))
    second = ingest_instrument(db_session, company, provider, date(2026, 1, 1), date(2026, 1, 3))
    assert first.records_inserted == 1
    assert second.records_inserted == 0
    assert second.records_updated == 1
    assert len(list(db_session.scalars(select(DailyMarketData)))) == 1


def test_duplicate_database_constraint(db_session):
    company = Company(name="Example", symbol="EXAMPLE", provider_symbol="EXAMPLE.NS", exchange="NSE", instrument_type="company")
    db_session.add(company)
    db_session.commit()
    values = row()
    for _ in range(2):
        db_session.add(DailyMarketData(company_id=company.id, provider="test", **values))
        if _ == 0:
            db_session.commit()
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_empty_provider_records_empty_run(db_session):
    company = Company(name="Example", symbol="EXAMPLE", provider_symbol="EXAMPLE.NS", exchange="NSE", instrument_type="company")
    db_session.add(company)
    db_session.commit()
    run = ingest_instrument(db_session, company, FakeProvider([]), date(2026, 1, 1), date(2026, 1, 3))
    assert run.status == "empty"
    assert run.records_inserted == 0
