from datetime import date
from decimal import Decimal

from app.db.models import Company, DailyMarketData


def add_company(db_session, symbol="NIFTY50", name="NIFTY 50", instrument_type="benchmark"):
    company = Company(name=name, symbol=symbol, provider_symbol="^NSEI", exchange="NSE", instrument_type=instrument_type)
    db_session.add(company)
    db_session.commit()
    return company


def add_record(db_session, company, trading_date, close):
    db_session.add(DailyMarketData(company_id=company.id, trading_date=trading_date, open=close, high=close, low=close, close=close, adjusted_close=close, volume=10, provider="test"))
    db_session.commit()


def test_market_overview_calculates_change(client, db_session):
    company = add_company(db_session)
    add_record(db_session, company, date(2026, 1, 1), Decimal("100"))
    add_record(db_session, company, date(2026, 1, 2), Decimal("110"))
    response = client.get("/api/v1/market/overview")
    assert response.status_code == 200
    snapshot = response.json()["instruments"][0]
    assert snapshot["latest_close"] == "110.000000"
    assert snapshot["absolute_change"] == "10.000000"
    assert snapshot["percentage_change"] == "10.000000"


def test_history_and_unknown_symbol(client, db_session):
    company = add_company(db_session, symbol="RELIANCE", name="Reliance Industries", instrument_type="company")
    add_record(db_session, company, date(2026, 1, 1), Decimal("100"))
    response = client.get("/api/v1/stocks/RELIANCE/history")
    assert response.status_code == 200
    assert len(response.json()["records"]) == 1
    assert client.get("/api/v1/stocks/UNKNOWN/history").status_code == 404


def test_health_endpoint_is_preserved(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
