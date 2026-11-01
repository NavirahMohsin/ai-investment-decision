"""Freshness classification for fundamental (reporting) data.

Thresholds are intentionally longer than market-quote freshness because
financial statements update on reporting cycles, not intraday.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum


class FundamentalFreshness(StrEnum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


# Defaults (days since provider retrieval)
DEFAULT_FRESH_DAYS = 30
DEFAULT_AGING_DAYS = 90


def classify_fundamental_freshness(
    retrieved_at: datetime | None,
    *,
    now: datetime | None = None,
    fresh_days: int = DEFAULT_FRESH_DAYS,
    aging_days: int = DEFAULT_AGING_DAYS,
) -> FundamentalFreshness:
    """
    Classify freshness from the provider retrieval timestamp.

    Distinguishes retrieval time from the financial reporting period end date.
    """
    if retrieved_at is None:
        return FundamentalFreshness.UNAVAILABLE
    current = now or datetime.now(timezone.utc)
    ts = retrieved_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (current - ts.astimezone(timezone.utc)).total_seconds() / 86400.0)
    if age_days <= fresh_days:
        return FundamentalFreshness.FRESH
    if age_days <= aging_days:
        return FundamentalFreshness.AGING
    return FundamentalFreshness.STALE
