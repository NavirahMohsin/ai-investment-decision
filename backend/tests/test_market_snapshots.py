"""Tests for market snapshot functionality."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Company, MarketSnapshot
from app.services.market_data import Freshness, store_market_snapshot
from app.services.providers.base import MarketQuote


def test_store_market_snapshot(db_session):
    """Test storing a market snapshot."""
    company = Company(
        name="Test Company",
        symbol="TEST",
        provider_symbol="TEST.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    quote: MarketQuote = {
        "price": Decimal("100.50"),
        "previous_close": Decimal("98.00"),
        "open": Decimal("99.00"),
        "day_high": Decimal("101.00"),
        "day_low": Decimal("98.50"),
        "volume": 1000000,
        "currency": "INR",
        "market_timestamp": datetime.now(timezone.utc),
        "retrieved_at": datetime.now(timezone.utc),
        "provider": "test_provider",
    }
    
    snapshot = store_market_snapshot(db_session, company, quote, Freshness.FRESH)
    
    assert snapshot.company_id == company.id
    assert snapshot.price == Decimal("100.50")
    assert snapshot.previous_close == Decimal("98.00")
    assert snapshot.open == Decimal("99.00")
    assert snapshot.high == Decimal("101.00")
    assert snapshot.low == Decimal("98.50")
    assert snapshot.volume == 1000000
    assert snapshot.freshness == "FRESH"
    assert snapshot.provider == "test_provider"
    
    # Verify absolute and percentage change
    assert snapshot.absolute_change == Decimal("2.50")
    # (2.50 / 98.00) * 100 ≈ 2.551020
    assert snapshot.percentage_change is not None
    assert abs(float(snapshot.percentage_change) - 2.551020) < 0.001


def test_store_snapshot_with_missing_previous_close(db_session):
    """Test storing snapshot when previous close is missing."""
    company = Company(
        name="Test Company",
        symbol="TEST",
        provider_symbol="TEST.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    quote: MarketQuote = {
        "price": Decimal("100.50"),
        "previous_close": None,
        "open": None,
        "day_high": None,
        "day_low": None,
        "volume": None,
        "currency": "INR",
        "market_timestamp": datetime.now(timezone.utc),
        "retrieved_at": datetime.now(timezone.utc),
        "provider": "test_provider",
    }
    
    snapshot = store_market_snapshot(db_session, company, quote, Freshness.STALE)
    
    assert snapshot.price == Decimal("100.50")
    assert snapshot.previous_close is None
    assert snapshot.absolute_change is None
    assert snapshot.percentage_change is None
    assert snapshot.freshness == "STALE"


def test_multiple_snapshots_per_company(db_session):
    """Test storing multiple snapshots for the same company."""
    company = Company(
        name="Test Company",
        symbol="TEST",
        provider_symbol="TEST.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    # Store three snapshots
    for i in range(3):
        quote: MarketQuote = {
            "price": Decimal(f"{100 + i}.00"),
            "previous_close": Decimal("98.00"),
            "open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "currency": "INR",
            "market_timestamp": datetime.now(timezone.utc),
            "retrieved_at": datetime.now(timezone.utc),
            "provider": "test_provider",
        }
        store_market_snapshot(db_session, company, quote, Freshness.FRESH)
    
    snapshots = list(
        db_session.scalars(
            select(MarketSnapshot)
            .where(MarketSnapshot.company_id == company.id)
            .order_by(MarketSnapshot.created_at)
        )
    )
    
    assert len(snapshots) == 3
    assert snapshots[0].price == Decimal("100.00")
    assert snapshots[1].price == Decimal("101.00")
    assert snapshots[2].price == Decimal("102.00")
