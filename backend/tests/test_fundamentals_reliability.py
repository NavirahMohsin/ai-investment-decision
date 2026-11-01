"""Reliability tests for fundamentals refresh, freshness, and caching."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import Company, FundamentalDataUpdateRun
from app.services.fundamentals import IngestionResult
from app.services.fundamentals_cache import FundamentalsCache
from app.services.fundamentals_freshness import FundamentalFreshness, classify_fundamental_freshness
from app.services.fundamentals_refresh import RefreshInProgressError, refresh_companies


@pytest.fixture
def company(db_session: Session) -> Company:
    c = Company(
        symbol="REL",
        name="Rel",
        provider_symbol="REL.NS",
        exchange="NSE",
        instrument_type="company",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


class TestFreshness:
    def test_unavailable(self):
        assert classify_fundamental_freshness(None) == FundamentalFreshness.UNAVAILABLE

    def test_fresh(self):
        now = datetime.now(timezone.utc)
        assert classify_fundamental_freshness(now - timedelta(days=5), now=now) == FundamentalFreshness.FRESH

    def test_aging(self):
        now = datetime.now(timezone.utc)
        assert classify_fundamental_freshness(now - timedelta(days=45), now=now) == FundamentalFreshness.AGING

    def test_stale(self):
        now = datetime.now(timezone.utc)
        assert classify_fundamental_freshness(now - timedelta(days=120), now=now) == FundamentalFreshness.STALE


class TestCache:
    def test_invalidate(self):
        cache = FundamentalsCache(ttl_seconds=60)
        cache.set("a", {"x": 1})
        assert cache.get("a") == {"x": 1}
        cache.invalidate_all()
        assert cache.get("a") is None


class TestRefresh:
    def test_per_company_isolation(self, db_session: Session, company: Company):
        other = Company(
            symbol="TCS",
            name="TCS",
            provider_symbol="TCS.NS",
            exchange="NSE",
            instrument_type="company",
        )
        db_session.add(other)
        db_session.commit()

        def fake_ingest(db, company, provider, **kwargs):
            if company.symbol == "REL":
                return IngestionResult(
                    company_symbol="REL",
                    success=False,
                    company_info_updated=False,
                    financials_inserted=0,
                    financials_updated=0,
                    ratios_inserted=0,
                    error="provider error",
                )
            return IngestionResult(
                company_symbol="TCS",
                success=True,
                company_info_updated=True,
                financials_inserted=1,
                financials_updated=0,
                ratios_inserted=1,
                error=None,
            )

        with patch(
            "app.services.fundamentals_refresh.ingest_company_fundamentals",
            side_effect=fake_ingest,
        ), patch(
            "app.services.fundamentals_refresh.YahooFinanceProvider",
            return_value=MagicMock(),
        ):
            run, results = refresh_companies(
                db_session,
                symbols=["REL", "TCS"],
                retries=0,
                max_companies=10,
            )

        assert run.status == "partial"
        assert run.successful_count == 1
        assert run.failed_count == 1
        assert "REL" in (run.failed_symbols or "")
        assert run.completed_at is not None

    def test_concurrent_lock(self, db_session: Session, company: Company):
        import app.services.fundamentals_refresh as fr

        acquired = fr._refresh_lock.acquire(blocking=False)
        assert acquired
        try:
            with pytest.raises(RefreshInProgressError):
                refresh_companies(db_session, symbols=["REL"], retries=0)
        finally:
            fr._refresh_lock.release()

    def test_run_tracking_persisted(self, db_session: Session, company: Company):
        with patch(
            "app.services.fundamentals_refresh.ingest_company_fundamentals",
            return_value=IngestionResult(
                company_symbol="REL",
                success=True,
                company_info_updated=True,
                financials_inserted=2,
                financials_updated=1,
                ratios_inserted=3,
                error=None,
            ),
        ), patch(
            "app.services.fundamentals_refresh.YahooFinanceProvider",
            return_value=MagicMock(),
        ):
            run, _ = refresh_companies(db_session, symbols=["REL"], retries=0)

        stored = db_session.get(FundamentalDataUpdateRun, run.id)
        assert stored is not None
        assert stored.status == "completed"
        assert stored.trigger_source == "manual"
