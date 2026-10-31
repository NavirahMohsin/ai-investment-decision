"""Tests for Indian exchange calendar."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.services.calendar import (
    MarketSession,
    get_market_session,
    is_trading_day,
    next_trading_day,
    previous_trading_day,
)

IST = ZoneInfo("Asia/Kolkata")


def test_weekend_not_trading_day():
    """Test that weekends are not trading days."""
    # Saturday, November 2, 2024
    saturday = date(2024, 11, 2)
    assert not is_trading_day(saturday)
    
    # Sunday, November 3, 2024
    sunday = date(2024, 11, 3)
    assert not is_trading_day(sunday)


def test_regular_weekday_is_trading_day():
    """Test that regular weekdays are trading days."""
    # Monday, November 4, 2024 (not a holiday)
    monday = date(2024, 11, 4)
    assert is_trading_day(monday)


def test_exchange_holiday_not_trading_day():
    """Test that declared holidays are not trading days."""
    # Republic Day 2025
    republic_day = date(2025, 1, 26)
    assert not is_trading_day(republic_day)
    
    # Independence Day 2025
    independence_day = date(2025, 8, 15)
    assert not is_trading_day(independence_day)
    
    # Christmas 2025
    christmas = date(2025, 12, 25)
    assert not is_trading_day(christmas)


def test_market_session_pre_open():
    """Test pre-open session detection."""
    # Monday at 9:10 AM IST
    dt = datetime(2024, 11, 4, 9, 10, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.PRE_OPEN


def test_market_session_open():
    """Test open session detection."""
    # Monday at 10:00 AM IST
    dt = datetime(2024, 11, 4, 10, 0, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.OPEN
    
    # Monday at 3:00 PM IST
    dt = datetime(2024, 11, 4, 15, 0, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.OPEN


def test_market_session_closed_after_hours():
    """Test closed session after market hours."""
    # Monday at 8:00 AM IST (before pre-open)
    dt = datetime(2024, 11, 4, 8, 0, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.CLOSED
    
    # Monday at 4:00 PM IST (after close)
    dt = datetime(2024, 11, 4, 16, 0, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.CLOSED


def test_market_session_closed_on_weekend():
    """Test that market is closed on weekends."""
    # Saturday at 10:00 AM IST
    dt = datetime(2024, 11, 2, 10, 0, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.CLOSED


def test_market_session_closed_on_holiday():
    """Test that market is closed on holidays."""
    # Republic Day 2025 at 10:00 AM IST
    dt = datetime(2025, 1, 26, 10, 0, 0, tzinfo=IST)
    session = get_market_session(dt)
    assert session == MarketSession.CLOSED


def test_next_trading_day_skips_weekend():
    """Test next trading day skips weekends."""
    # Friday, November 1, 2024
    friday = date(2024, 11, 1)
    next_day = next_trading_day(friday)
    
    # Should be Monday, November 4, 2024
    assert next_day == date(2024, 11, 4)
    assert next_day.weekday() == 0  # Monday


def test_next_trading_day_skips_holiday():
    """Test next trading day skips holidays."""
    # Day before Republic Day 2025
    before_holiday = date(2025, 1, 25)
    next_day = next_trading_day(before_holiday)
    
    # Should skip Sunday Jan 26 (Republic Day) and land on Monday Jan 27
    assert next_day == date(2025, 1, 27)


def test_previous_trading_day_skips_weekend():
    """Test previous trading day skips weekends."""
    # Monday, November 4, 2024
    monday = date(2024, 11, 4)
    prev_day = previous_trading_day(monday)
    
    # Should skip Sunday, Saturday, Friday Nov 1 (Diwali) and land on Thursday, October 31
    assert prev_day == date(2024, 10, 31)
    assert prev_day.weekday() == 3  # Thursday


def test_previous_trading_day_skips_holiday():
    """Test previous trading day skips holidays."""
    # Day after Republic Day 2025
    after_holiday = date(2025, 1, 27)
    prev_day = previous_trading_day(after_holiday)
    
    # Should skip Sunday Jan 26 (Republic Day) and land on Friday Jan 24
    assert prev_day == date(2025, 1, 24)
