"""Indian stock exchange calendar and market hours."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class MarketSession(StrEnum):
    """Market session status."""
    PRE_OPEN = "PRE_OPEN"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


# NSE/BSE trading holidays for 2024-2027 (major holidays)
# Source: NSE/BSE circulars - should be updated annually
EXCHANGE_HOLIDAYS = {
    # 2024
    date(2024, 1, 26): "Republic Day",
    date(2024, 3, 8): "Mahashivratri",
    date(2024, 3, 25): "Holi",
    date(2024, 3, 29): "Good Friday",
    date(2024, 4, 11): "Id-ul-Fitr",
    date(2024, 4, 17): "Ram Navami",
    date(2024, 4, 21): "Mahavir Jayanti",
    date(2024, 5, 1): "Maharashtra Day",
    date(2024, 6, 17): "Bakri Id",
    date(2024, 7, 17): "Muharram",
    date(2024, 8, 15): "Independence Day",
    date(2024, 8, 26): "Ganesh Chaturthi",
    date(2024, 10, 2): "Mahatma Gandhi Jayanti",
    date(2024, 10, 12): "Dussehra",
    date(2024, 11, 1): "Diwali Laxmi Pujan",
    date(2024, 11, 2): "Diwali Balipratipada",
    date(2024, 11, 15): "Gurunanak Jayanti",
    date(2024, 12, 25): "Christmas",
    
    # 2025
    date(2025, 1, 26): "Republic Day",
    date(2025, 2, 26): "Mahashivratri",
    date(2025, 3, 14): "Holi",
    date(2025, 3, 31): "Id-ul-Fitr",
    date(2025, 4, 10): "Mahavir Jayanti",
    date(2025, 4, 14): "Dr. Ambedkar Jayanti",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 1): "Maharashtra Day",
    date(2025, 6, 7): "Bakri Id",
    date(2025, 7, 6): "Muharram",
    date(2025, 8, 15): "Independence Day",
    date(2025, 8, 27): "Ganesh Chaturthi",
    date(2025, 10, 2): "Mahatma Gandhi Jayanti / Dussehra",
    date(2025, 10, 20): "Diwali Balipratipada",
    date(2025, 10, 21): "Diwali Laxmi Pujan",
    date(2025, 11, 5): "Gurunanak Jayanti",
    date(2025, 12, 25): "Christmas",
    
    # 2026
    date(2026, 1, 26): "Republic Day",
    date(2026, 2, 16): "Mahashivratri",
    date(2026, 3, 4): "Holi",
    date(2026, 3, 20): "Id-ul-Fitr",
    date(2026, 3, 30): "Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday",
    date(2026, 4, 6): "Ram Navami",
    date(2026, 4, 14): "Dr. Ambedkar Jayanti",
    date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id",
    date(2026, 6, 25): "Muharram",
    date(2026, 8, 15): "Independence Day",
    date(2026, 9, 16): "Ganesh Chaturthi",
    date(2026, 10, 2): "Mahatma Gandhi Jayanti",
    date(2026, 10, 21): "Dussehra",
    date(2026, 11, 8): "Diwali Balipratipada",
    date(2026, 11, 9): "Diwali Laxmi Pujan",
    date(2026, 11, 24): "Gurunanak Jayanti",
    date(2026, 12, 25): "Christmas",
    
    # 2027
    date(2027, 1, 26): "Republic Day",
    date(2027, 3, 5): "Mahashivratri",
    date(2027, 3, 10): "Id-ul-Fitr",
    date(2027, 3, 22): "Holi",
    date(2027, 3, 26): "Good Friday",
    date(2027, 3, 26): "Ram Navami",
    date(2027, 4, 19): "Mahavir Jayanti",
    date(2027, 5, 1): "Maharashtra Day",
    date(2027, 5, 17): "Bakri Id",
    date(2027, 6, 15): "Muharram",
    date(2027, 8, 15): "Independence Day",
    date(2027, 9, 5): "Ganesh Chaturthi",
    date(2027, 10, 2): "Mahatma Gandhi Jayanti",
    date(2027, 10, 10): "Dussehra",
    date(2027, 10, 28): "Diwali Laxmi Pujan",
    date(2027, 10, 29): "Diwali Balipratipada",
    date(2027, 11, 13): "Gurunanak Jayanti",
    date(2027, 12, 25): "Christmas",
}


# Regular market timings (Monday-Friday)
PRE_OPEN_START = time(9, 0, 0)
PRE_OPEN_END = time(9, 15, 0)
MARKET_OPEN = time(9, 15, 0)
MARKET_CLOSE = time(15, 30, 0)


def is_trading_day(check_date: date) -> bool:
    """Check if a date is a trading day (not weekend or holiday)."""
    # Check if weekend (Saturday=5, Sunday=6)
    if check_date.weekday() >= 5:
        return False
    
    # Check if listed holiday
    if check_date in EXCHANGE_HOLIDAYS:
        return False
    
    return True


def get_market_session(at: datetime | None = None) -> MarketSession:
    """
    Get current market session status.
    
    Args:
        at: Optional datetime to check. Defaults to current time.
    
    Returns:
        MarketSession enum value
    """
    current = (at or datetime.now(timezone.utc)).astimezone(IST)
    current_date = current.date()
    current_time = current.time()
    
    # Check if it's a trading day
    if not is_trading_day(current_date):
        return MarketSession.CLOSED
    
    # Check session times
    if PRE_OPEN_START <= current_time < PRE_OPEN_END:
        return MarketSession.PRE_OPEN
    elif MARKET_OPEN <= current_time < MARKET_CLOSE:
        return MarketSession.OPEN
    else:
        return MarketSession.CLOSED


def next_trading_day(from_date: date) -> date:
    """Get the next trading day after the given date."""
    from datetime import timedelta
    
    check = from_date + timedelta(days=1)
    
    # Limit search to 30 days to prevent infinite loops
    for _ in range(30):
        if is_trading_day(check):
            return check
        check += timedelta(days=1)
    
    # Fallback if no trading day found in 30 days
    return check


def previous_trading_day(from_date: date) -> date:
    """Get the previous trading day before the given date."""
    from datetime import timedelta
    
    check = from_date - timedelta(days=1)
    
    # Limit search to 30 days
    for _ in range(30):
        if is_trading_day(check):
            return check
        check -= timedelta(days=1)
    
    # Fallback if no trading day found in 30 days
    return check
