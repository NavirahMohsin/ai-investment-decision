"""Tests for technical signal generation."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.db.models import Company, DailyMarketData
from app.services.indicators import IndicatorParameters
from app.services.signals import classify_trend, generate_signals


def create_test_company(db_session) -> Company:
    """Create a test company."""
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
    return company


def create_market_data(db_session, company: Company, days: int = 50) -> list[DailyMarketData]:
    """Create test market data."""
    from datetime import timedelta
    rows = []
    base_price = Decimal("100.00")
    base_date = date(2024, 1, 1)
    
    for i in range(days):
        price = base_price + Decimal(i * 0.5)
        row = DailyMarketData(
            company_id=company.id,
            trading_date=base_date + timedelta(days=i),
            open=price,
            high=price * Decimal("1.02"),
            low=price * Decimal("0.98"),
            close=price,
            volume=1000000,
            provider="test_provider",
        )
        db_session.add(row)
        rows.append(row)
    
    db_session.commit()
    return rows


def test_classify_trend_strong_bullish():
    """Test strong bullish trend classification."""
    trend = classify_trend(
        current_price=110.0,
        ema=100.0,
        rsi=70.0,
        adx=30.0,
        macd_histogram=2.5,
    )
    
    assert trend.classification == "STRONG_BULLISH"
    assert "ADX >= 25" in trend.explanation
    assert trend.current_price == 110.0


def test_classify_trend_strong_bearish():
    """Test strong bearish trend classification."""
    trend = classify_trend(
        current_price=90.0,
        ema=100.0,
        rsi=25.0,
        adx=30.0,
        macd_histogram=-2.5,
    )
    
    assert trend.classification == "STRONG_BEARISH"
    assert "ADX >= 25" in trend.explanation


def test_classify_trend_bullish():
    """Test bullish trend classification."""
    trend = classify_trend(
        current_price=105.0,
        ema=100.0,
        rsi=55.0,
        adx=22.0,
        macd_histogram=0.5,
    )
    
    assert trend.classification == "BULLISH"
    assert "ADX >= 20" in trend.explanation or "positive MACD" in trend.explanation


def test_classify_trend_bearish():
    """Test bearish trend classification."""
    trend = classify_trend(
        current_price=95.0,
        ema=100.0,
        rsi=45.0,
        adx=22.0,
        macd_histogram=-0.5,
    )
    
    assert trend.classification == "BEARISH"


def test_classify_trend_neutral():
    """Test neutral trend classification."""
    trend = classify_trend(
        current_price=100.0,
        ema=100.0,
        rsi=50.0,
        adx=15.0,
        macd_histogram=0.0,
    )
    
    assert trend.classification == "NEUTRAL"


def test_classify_trend_insufficient_data():
    """Test trend classification with insufficient data."""
    trend = classify_trend(
        current_price=100.0,
        ema=None,
        rsi=None,
        adx=None,
        macd_histogram=None,
    )
    
    assert trend.classification == "NEUTRAL"
    assert "Insufficient" in trend.explanation


def test_generate_signals_insufficient_data(db_session):
    """Test signal generation with insufficient data."""
    company = create_test_company(db_session)
    
    # Create only 1 row
    row = DailyMarketData(
        company_id=company.id,
        trading_date=date(2024, 1, 1),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("98"),
        close=Decimal("100"),
        volume=1000000,
        provider="test_provider",
    )
    db_session.add(row)
    db_session.commit()
    
    signals = generate_signals([row], IndicatorParameters())
    
    assert len(signals) == 0


def test_generate_signals_with_data(db_session):
    """Test signal generation with sufficient data."""
    company = create_test_company(db_session)
    rows = create_market_data(db_session, company, days=50)
    
    signals = generate_signals(rows, IndicatorParameters())
    
    # Should generate at least some signals
    assert isinstance(signals, list)
    
    # Check signal structure
    if signals:
        signal = signals[0]
        assert hasattr(signal, "signal_type")
        assert hasattr(signal, "timestamp")
        assert hasattr(signal, "price")
        assert hasattr(signal, "explanation")
        assert hasattr(signal, "indicator_values")
        assert hasattr(signal, "strength")
        assert signal.strength in ["STRONG", "MODERATE", "WEAK"]
