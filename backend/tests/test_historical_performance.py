"""Tests for historical financial performance analysis."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial
from app.services.historical_performance import (
    SeriesQuality,
    TrendDirection,
    analyze_historical_performance,
    build_metric_series,
    calculate_growth,
)


@pytest.fixture
def company(db_session: Session) -> Company:
    c = Company(
        symbol="HIST",
        name="History Co",
        provider_symbol="HIST.NS",
        exchange="NSE",
        sector="Technology",
        instrument_type="company",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def _add_metric(
    db: Session,
    company_id: int,
    name: str,
    value: Decimal | None,
    period_end: date,
    period_type: str = "annual",
    statement_type: str = "income",
    currency: str = "INR",
) -> None:
    db.add(
        CompanyFinancial(
            company_id=company_id,
            metric_name=name,
            metric_value=value,
            period_end=period_end,
            period_type=period_type,
            statement_type=statement_type,
            currency=currency,
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc),
        )
    )


class TestGrowthCalculations:
    def test_normal_growth(self):
        rate, err = calculate_growth(Decimal("120"), Decimal("100"))
        assert err is None
        assert rate == Decimal("0.2")

    def test_negative_growth(self):
        rate, err = calculate_growth(Decimal("80"), Decimal("100"))
        assert err is None
        assert rate == Decimal("-0.2")

    def test_missing_values(self):
        rate, err = calculate_growth(None, Decimal("100"))
        assert rate is None
        assert err is not None

    def test_zero_previous(self):
        rate, err = calculate_growth(Decimal("50"), Decimal("0"))
        assert rate is None
        assert "zero" in (err or "").lower()

    def test_negative_values_allowed(self):
        rate, err = calculate_growth(Decimal("-50"), Decimal("-100"))
        assert err is None
        assert rate == Decimal("-0.5")


class TestRevenueHistory:
    def test_revenue_yoy_growth(self, db_session: Session, company: Company):
        _add_metric(db_session, company.id, "Total Revenue", Decimal("100"), date(2021, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", Decimal("120"), date(2022, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", Decimal("150"), date(2023, 3, 31))
        db_session.commit()

        series = build_metric_series(db_session, company, "revenue", "Revenue", "annual")
        assert len(series.observations) == 3
        assert len(series.growth) == 2
        assert series.growth[0].growth_pct == Decimal("20")
        assert series.growth[1].growth_pct == Decimal("25")
        assert series.growth[0].is_derived is True
        assert series.trend in {
            TrendDirection.IMPROVING,
            TrendDirection.ACCELERATING,
        }

    def test_revenue_acceleration(self, db_session: Session, company: Company):
        _add_metric(db_session, company.id, "Total Revenue", Decimal("100"), date(2021, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", Decimal("110"), date(2022, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", Decimal("143"), date(2023, 3, 31))
        db_session.commit()

        series = build_metric_series(db_session, company, "revenue", "Revenue", "annual")
        assert any("acceleration" in n.lower() for n in series.notes) or series.trend == TrendDirection.ACCELERATING


class TestMissingPeriods:
    def test_missing_annual_year(self, db_session: Session, company: Company):
        _add_metric(db_session, company.id, "Total Revenue", Decimal("100"), date(2021, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", Decimal("150"), date(2023, 3, 31))
        db_session.commit()

        series = build_metric_series(db_session, company, "revenue", "Revenue", "annual")
        assert series.quality == SeriesQuality.INCOMPLETE
        assert "2022" in series.missing_periods

    def test_null_value_preserved(self, db_session: Session, company: Company):
        _add_metric(db_session, company.id, "Total Revenue", Decimal("100"), date(2021, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", None, date(2022, 3, 31))
        _add_metric(db_session, company.id, "Total Revenue", Decimal("130"), date(2023, 3, 31))
        db_session.commit()

        series = build_metric_series(db_session, company, "revenue", "Revenue", "annual")
        assert series.observations[1].value is None
        # Growth involving null should error, not invent
        mid = [g for g in series.growth if g.period_end == date(2022, 3, 31)]
        assert mid and mid[0].growth_rate is None


class TestQuarterlyComparisons:
    def test_same_quarter_yoy(self, db_session: Session, company: Company):
        # Q1 FY-style March ends
        _add_metric(
            db_session, company.id, "Total Revenue", Decimal("100"), date(2022, 3, 31), "quarterly"
        )
        _add_metric(
            db_session, company.id, "Total Revenue", Decimal("110"), date(2022, 6, 30), "quarterly"
        )
        _add_metric(
            db_session, company.id, "Total Revenue", Decimal("120"), date(2023, 3, 31), "quarterly"
        )
        db_session.commit()

        series = build_metric_series(
            db_session, company, "revenue", "Revenue", "quarterly", include_qoq=True
        )
        yoy = [g for g in series.growth if g.comparison_type == "same_quarter_yoy"]
        assert len(yoy) == 1
        assert yoy[0].growth_pct == Decimal("20")

    def test_does_not_mix_annual_and_quarterly(self, db_session: Session, company: Company):
        _add_metric(db_session, company.id, "Total Revenue", Decimal("400"), date(2023, 3, 31), "annual")
        _add_metric(
            db_session, company.id, "Total Revenue", Decimal("100"), date(2023, 3, 31), "quarterly"
        )
        db_session.commit()

        annual = build_metric_series(db_session, company, "revenue", "Revenue", "annual")
        quarterly = build_metric_series(db_session, company, "revenue", "Revenue", "quarterly")
        assert len(annual.observations) == 1
        assert annual.observations[0].value == Decimal("400")
        assert len(quarterly.observations) == 1
        assert quarterly.observations[0].value == Decimal("100")


class TestFullReport:
    def test_profitability_and_cash_flow(self, db_session: Session, company: Company):
        for year, rev, gp, oi, ni, eps, ocf, capex in [
            (2021, 1000, 400, 200, 150, 10, 180, -50),
            (2022, 1100, 450, 220, 160, 11, 190, -55),
            (2023, 1250, 520, 260, 190, 13, 220, -60),
        ]:
            pe = date(year, 3, 31)
            _add_metric(db_session, company.id, "Total Revenue", Decimal(rev), pe)
            _add_metric(db_session, company.id, "Gross Profit", Decimal(gp), pe)
            _add_metric(db_session, company.id, "Operating Income", Decimal(oi), pe)
            _add_metric(db_session, company.id, "Net Income", Decimal(ni), pe)
            _add_metric(db_session, company.id, "Basic EPS", Decimal(eps), pe)
            _add_metric(
                db_session,
                company.id,
                "Operating Cash Flow",
                Decimal(ocf),
                pe,
                statement_type="cashflow",
            )
            _add_metric(
                db_session,
                company.id,
                "Capital Expenditure",
                Decimal(capex),
                pe,
                statement_type="cashflow",
            )
            _add_metric(
                db_session,
                company.id,
                "Total Assets",
                Decimal(year * 100),
                pe,
                statement_type="balance",
            )
            _add_metric(
                db_session,
                company.id,
                "Total Debt",
                Decimal(200),
                pe,
                statement_type="balance",
            )
            _add_metric(
                db_session,
                company.id,
                "Stockholders Equity",
                Decimal(500 + year),
                pe,
                statement_type="balance",
            )
            _add_metric(
                db_session,
                company.id,
                "Current Assets",
                Decimal(300),
                pe,
                statement_type="balance",
            )
            _add_metric(
                db_session,
                company.id,
                "Current Liabilities",
                Decimal(150),
                pe,
                statement_type="balance",
            )
        db_session.commit()

        report = analyze_historical_performance(db_session, company, "annual")
        assert report.symbol == "HIST"
        assert len(report.revenue.observations) == 3
        assert report.gross_margin.observations[-1].source == "calculated"
        assert report.gross_margin.observations[-1].value is not None
        assert report.free_cash_flow.observations[-1].value is not None
        assert len(report.cash_conversion) == 3
        assert report.cash_conversion[-1].ocf_to_ni is not None
        assert report.eps.growth[-1].growth_pct is not None

    def test_empty_company(self, db_session: Session, company: Company):
        report = analyze_historical_performance(db_session, company, "annual")
        assert report.revenue.quality == SeriesQuality.EMPTY
        assert "No revenue history" in " ".join(report.data_warnings) or report.data_warnings
