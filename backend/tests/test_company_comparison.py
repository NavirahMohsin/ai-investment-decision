"""Tests for company comparison service."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo
from app.services.company_comparison import (
    ComparisonValidationError,
    compare_companies,
    resolve_comparison_companies,
)


def _company(db: Session, symbol: str, sector: str = "Technology", instrument_type: str = "company") -> Company:
    c = Company(
        symbol=symbol,
        name=f"{symbol} Ltd",
        provider_symbol=f"{symbol}.NS",
        exchange="NSE",
        sector=sector,
        instrument_type=instrument_type,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _seed(db: Session, company: Company, revenue: int, currency: str = "INR", year: int = 2023) -> None:
    pe = date(year, 3, 31)
    for name, value, st in [
        ("Total Revenue", revenue, "income"),
        ("Gross Profit", revenue // 2, "income"),
        ("Operating Income", revenue // 4, "income"),
        ("Net Income", revenue // 5, "income"),
        ("Basic EPS", 10, "income"),
        ("Total Revenue", revenue - 100, "income"),  # will conflict - skip
    ]:
        pass
    # Prior year for growth
    pe_prev = date(year - 1, 3, 31)
    for pe_x, rev in [(pe_prev, revenue - 200), (pe, revenue)]:
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Total Revenue",
                metric_value=Decimal(rev),
                period_end=pe_x,
                period_type="annual",
                statement_type="income",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Net Income",
                metric_value=Decimal(rev // 5),
                period_end=pe_x,
                period_type="annual",
                statement_type="income",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Gross Profit",
                metric_value=Decimal(rev // 2),
                period_end=pe_x,
                period_type="annual",
                statement_type="income",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Operating Income",
                metric_value=Decimal(rev // 4),
                period_end=pe_x,
                period_type="annual",
                statement_type="income",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Basic EPS",
                metric_value=Decimal("10"),
                period_end=pe_x,
                period_type="annual",
                statement_type="income",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Operating Cash Flow",
                metric_value=Decimal(rev // 4),
                period_end=pe_x,
                period_type="annual",
                statement_type="cashflow",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Stockholders Equity",
                metric_value=Decimal("800"),
                period_end=pe_x,
                period_type="annual",
                statement_type="balance",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Total Debt",
                metric_value=Decimal("200"),
                period_end=pe_x,
                period_type="annual",
                statement_type="balance",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Total Assets",
                metric_value=Decimal("1500"),
                period_end=pe_x,
                period_type="annual",
                statement_type="balance",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Current Assets",
                metric_value=Decimal("500"),
                period_end=pe_x,
                period_type="annual",
                statement_type="balance",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name="Current Liabilities",
                metric_value=Decimal("250"),
                period_end=pe_x,
                period_type="annual",
                statement_type="balance",
                currency=currency,
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    db.add(
        CompanyFundamentalInfo(
            company_id=company.id,
            currency=currency,
            market_cap=1_000_000,
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


class TestValidation:
    def test_duplicate_symbols_normalized(self, db_session: Session):
        a = _company(db_session, "AAA")
        b = _company(db_session, "BBB")
        _seed(db_session, a, 1000)
        _seed(db_session, b, 2000)
        companies = resolve_comparison_companies(db_session, ["AAA", "aaa", "BBB"])
        assert len(companies) == 2

    def test_unknown_symbol(self, db_session: Session):
        _company(db_session, "AAA")
        with pytest.raises(ComparisonValidationError, match="Unknown"):
            resolve_comparison_companies(db_session, ["AAA", "ZZZ"])

    def test_index_excluded(self, db_session: Session):
        _company(db_session, "AAA")
        _company(db_session, "NIFTY", instrument_type="benchmark")
        with pytest.raises(ComparisonValidationError, match="Indices"):
            resolve_comparison_companies(db_session, ["AAA", "NIFTY"])

    def test_requires_two(self, db_session: Session):
        _company(db_session, "AAA")
        with pytest.raises(ComparisonValidationError, match="two"):
            resolve_comparison_companies(db_session, ["AAA"])


class TestComparison:
    def test_multi_company(self, db_session: Session):
        a = _company(db_session, "AAA", sector="Technology")
        b = _company(db_session, "BBB", sector="Technology")
        _seed(db_session, a, 1000)
        _seed(db_session, b, 2000)
        result = compare_companies(db_session, ["AAA", "BBB"])
        assert result.symbols == ["AAA", "BBB"]
        rev = next(m for m in result.metrics if m.key == "revenue")
        assert rev.values["BBB"] == Decimal("2000")
        assert rev.ranking is not None
        assert rev.ranking[0] == "BBB"
        assert "AAA" in rev.ranking

    def test_missing_metrics_excluded_from_rank(self, db_session: Session):
        a = _company(db_session, "AAA")
        b = _company(db_session, "BBB")
        _seed(db_session, a, 1000)
        # BBB has no financials
        db_session.add(
            CompanyFundamentalInfo(
                company_id=b.id,
                currency="INR",
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        result = compare_companies(db_session, ["AAA", "BBB"])
        rev = next(m for m in result.metrics if m.key == "revenue")
        assert rev.values["BBB"] is None
        assert "BBB" in rev.companies_excluded
        # No artificial last place — ranking None or only AAA not ranked alone as ordered list with fake values
        if rev.ranking is not None:
            assert "BBB" not in rev.ranking

    def test_different_currencies_warning(self, db_session: Session):
        a = _company(db_session, "AAA")
        b = _company(db_session, "BBB")
        _seed(db_session, a, 1000, currency="INR")
        _seed(db_session, b, 2000, currency="USD")
        result = compare_companies(db_session, ["AAA", "BBB"])
        assert any("currencies" in w.lower() for w in result.comparability_warnings)
        rev = next(m for m in result.metrics if m.key == "revenue")
        assert rev.comparable is False
        assert rev.ranking is None

    def test_different_sectors_warning(self, db_session: Session):
        a = _company(db_session, "AAA", sector="Technology")
        b = _company(db_session, "BBB", sector="Energy")
        _seed(db_session, a, 1000)
        _seed(db_session, b, 2000)
        result = compare_companies(db_session, ["AAA", "BBB"])
        assert result.sector_warning is not None
        assert "sectors" in result.sector_warning.lower()

    def test_different_periods_warning(self, db_session: Session):
        a = _company(db_session, "AAA")
        b = _company(db_session, "BBB")
        _seed(db_session, a, 1000, year=2023)
        _seed(db_session, b, 2000, year=2022)
        result = compare_companies(db_session, ["AAA", "BBB"])
        assert any("period" in w.lower() for w in result.comparability_warnings)

    def test_valuation_not_auto_ranked(self, db_session: Session):
        a = _company(db_session, "AAA")
        b = _company(db_session, "BBB")
        _seed(db_session, a, 1000)
        _seed(db_session, b, 2000)
        result = compare_companies(db_session, ["AAA", "BBB"])
        pe = next(m for m in result.metrics if m.key == "pe_ratio")
        assert pe.ranking is None
        assert pe.incomparable_reason is not None
