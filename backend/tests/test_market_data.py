from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.market_data import Freshness, MarketSession, classify_freshness, market_session


def test_freshness_is_explicit():
    now = datetime.now(timezone.utc)
    assert classify_freshness(now, now) == Freshness.FRESH
    assert classify_freshness(now - timedelta(minutes=10), now) == Freshness.DELAYED
    assert classify_freshness(now - timedelta(hours=1), now) == Freshness.STALE
    assert classify_freshness(None, now) == Freshness.UNAVAILABLE


def test_indian_market_session_handles_weekend_and_session_hours():
    assert market_session(datetime(2026, 1, 3, 10, tzinfo=timezone.utc)) == MarketSession.CLOSED
    assert market_session(datetime(2026, 1, 5, 3, 30, tzinfo=timezone.utc)) == MarketSession.PRE_OPEN
    assert market_session(datetime(2026, 1, 5, 5, tzinfo=timezone.utc)) == MarketSession.OPEN
    assert market_session(datetime(2026, 1, 5, 11, tzinfo=timezone.utc)) == MarketSession.CLOSED


def test_quote_change_fields_are_not_zero_fallbacks():
    from app.services.market_data import quote_response_fields

    fields = quote_response_fields(
        {
            "price": Decimal("110"),
            "previous_close": Decimal("100"),
            "open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "currency": None,
            "market_timestamp": datetime.now(timezone.utc),
            "retrieved_at": datetime.now(timezone.utc),
            "provider": "yahoo_finance",
        }
    )
    assert fields["absolute_change"] == Decimal("10")
    assert fields["open"] is None
