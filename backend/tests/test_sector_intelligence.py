from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo, CompanyProfile, DailyMarketData, Sector


def _seed_sector(db: Session) -> None:
    sector = Sector(
        sector_name="Technology",
        industry_name="Software",
        data_source="yahoo_finance",
        retrieved_at=datetime.now(timezone.utc),
    )
    db.add(sector)
    db.flush()
    for symbol, close, previous in [("AAA", Decimal("110"), Decimal("100")), ("BBB", Decimal("90"), Decimal("100"))]:
        company = Company(
            name=f"{symbol} Systems",
            symbol=symbol,
            provider_symbol=f"{symbol}.NS",
            exchange="NSE",
            sector="Technology",
            sector_id=sector.id,
            instrument_type="company",
        )
        db.add(company)
        db.flush()
        db.add(
            CompanyFundamentalInfo(
                company_id=company.id,
                market_cap=1_000_000,
                currency="INR",
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyProfile(
                company_id=company.id,
                industry="Software",
                headquarters_country="India",
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add_all(
            [
                DailyMarketData(
                    company_id=company.id,
                    trading_date=date(2025, 1, 2),
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=100,
                    provider="yahoo_finance",
                ),
                DailyMarketData(
                    company_id=company.id,
                    trading_date=date(2025, 1, 1),
                    open=previous,
                    high=previous,
                    low=previous,
                    close=previous,
                    volume=100,
                    provider="yahoo_finance",
                ),
            ]
        )
    db.commit()


def test_sector_list_and_intelligence(client, db_session: Session):
    _seed_sector(db_session)
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    assert response.json()[0]["company_count"] == 2

    response = client.get("/api/v1/sectors/Technology")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_scope"] == "tracked_universe"
    assert payload["tracked_company_count"] == 2
    assert payload["average_daily_change_pct"] is not None
    assert payload["warnings"]


def test_company_profile_endpoint(client, db_session: Session):
    _seed_sector(db_session)
    response = client.get("/api/v1/companies/AAA/profile")
    assert response.status_code == 200
    payload = response.json()
    assert payload["industry"] == "Software"
    assert payload["headquarters_country"] == "India"


def test_missing_sector_is_not_fabricated(client):
    response = client.get("/api/v1/sectors/Unknown")
    assert response.status_code == 404
