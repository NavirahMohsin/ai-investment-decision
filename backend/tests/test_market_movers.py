"""Tests for market movers functionality."""
from datetime import date
from decimal import Decimal

import pytest

from app.db.models import Company, DailyMarketData
from app.services.market_data import get_market_movers


def create_test_companies(db_session, count: int = 5) -> list[Company]:
    """Create test companies."""
    companies = []
    for i in range(count):
        company = Company(
            name=f"Company {i}",
            symbol=f"TEST{i}",
            provider_symbol=f"TEST{i}.NS",
            exchange="NSE",
            instrument_type="company",
            is_active=True,
        )
        db_session.add(company)
        companies.append(company)
    
    db_session.commit()
    return companies


def add_price_data(db_session, company: Company, date1: date, price1: Decimal, date2: date, price2: Decimal):
    """Add two days of price data for a company."""
    for trading_date, close_price in [(date1, price1), (date2, price2)]:
        row = DailyMarketData(
            company_id=company.id,
            trading_date=trading_date,
            open=close_price,
            high=close_price * Decimal("1.02"),
            low=close_price * Decimal("0.98"),
            close=close_price,
            volume=1000000 if trading_date == date2 else 800000,
            provider="test_provider",
        )
        db_session.add(row)
    
    db_session.commit()


def test_get_market_movers_empty_database(db_session):
    """Test market movers with no data."""
    movers = get_market_movers(db_session, limit=10)
    
    assert "gainers" in movers
    assert "losers" in movers
    assert "most_active" in movers
    assert len(movers["gainers"]) == 0
    assert len(movers["losers"]) == 0
    assert len(movers["most_active"]) == 0


def test_get_market_movers_with_data(db_session):
    """Test market movers with price data."""
    companies = create_test_companies(db_session, count=5)
    
    # Create different scenarios
    date1, date2 = date(2024, 1, 1), date(2024, 1, 2)
    
    # Gainer: +10%
    add_price_data(db_session, companies[0], date1, Decimal("100"), date2, Decimal("110"))
    
    # Another gainer: +5%
    add_price_data(db_session, companies[1], date1, Decimal("200"), date2, Decimal("210"))
    
    # Loser: -10%
    add_price_data(db_session, companies[2], date1, Decimal("150"), date2, Decimal("135"))
    
    # Flat
    add_price_data(db_session, companies[3], date1, Decimal("300"), date2, Decimal("300"))
    
    # Small loser: -2%
    add_price_data(db_session, companies[4], date1, Decimal("500"), date2, Decimal("490"))
    
    movers = get_market_movers(db_session, limit=10)
    
    # Check gainers
    assert len(movers["gainers"]) >= 2
    assert movers["gainers"][0]["symbol"] == "TEST0"  # Largest gainer
    assert movers["gainers"][0]["change_pct"] > 9.9
    
    # Check losers
    assert len(movers["losers"]) >= 2
    assert movers["losers"][0]["symbol"] == "TEST2"  # Largest loser
    assert movers["losers"][0]["change_pct"] < -9.9
    
    # Check most active
    assert len(movers["most_active"]) >= 1


def test_get_market_movers_limit(db_session):
    """Test market movers limit parameter."""
    companies = create_test_companies(db_session, count=10)
    
    date1, date2 = date(2024, 1, 1), date(2024, 1, 2)
    
    # Create many gainers
    for i, company in enumerate(companies):
        gain_pct = i + 1
        start_price = Decimal("100")
        end_price = start_price * (Decimal("1") + Decimal(gain_pct) / Decimal("100"))
        add_price_data(db_session, company, date1, start_price, date2, end_price)
    
    movers = get_market_movers(db_session, limit=3)
    
    # Should respect limit
    assert len(movers["gainers"]) <= 3
    assert len(movers["losers"]) <= 3
    assert len(movers["most_active"]) <= 3


def test_get_market_movers_inactive_company(db_session):
    """Test that inactive companies are excluded."""
    company = Company(
        name="Inactive Company",
        symbol="INACTIVE",
        provider_symbol="INACTIVE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=False,  # Inactive
    )
    db_session.add(company)
    db_session.commit()
    
    date1, date2 = date(2024, 1, 1), date(2024, 1, 2)
    add_price_data(db_session, company, date1, Decimal("100"), date2, Decimal("200"))
    
    movers = get_market_movers(db_session, limit=10)
    
    # Inactive company should not appear
    for gainer in movers["gainers"]:
        assert gainer["symbol"] != "INACTIVE"
