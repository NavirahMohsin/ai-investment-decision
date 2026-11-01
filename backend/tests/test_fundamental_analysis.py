"""Tests for fundamental analysis and scoring."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo
from app.services.fundamental_analysis import Classification, analyze_fundamentals
from app.services.fundamental_scoring import (
    DIMENSION_WEIGHTS,
    MIN_DIMENSIONS_REQUIRED,
    SCORING_VERSION,
    calculate_fundamental_score,
    score_from_analysis,
)
from app.services.sector_rules import SectorProfile, resolve_sector_rules


@pytest.fixture
def company(db_session: Session) -> Company:
    c = Company(
        symbol="FUND",
        name="Fund Co",
        provider_symbol="FUND.NS",
        exchange="NSE",
        sector="Technology",
        instrument_type="company",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def _fin(
    db: Session,
    company_id: int,
    name: str,
    value: Decimal | None,
    period_end: date,
    statement_type: str = "income",
    period_type: str = "annual",
) -> None:
    db.add(
        CompanyFinancial(
            company_id=company_id,
            metric_name=name,
            metric_value=value,
            period_end=period_end,
            period_type=period_type,
            statement_type=statement_type,
            currency="INR",
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc),
        )
    )


def _seed_strong_company(db: Session, company: Company) -> None:
    for year, rev, gp, oi, ni, eps, ocf, capex, assets, equity, debt, ca, cl in [
        (2021, 1000, 450, 250, 180, 12, 200, -40, 2000, 900, 300, 700, 300),
        (2022, 1200, 540, 300, 220, 15, 240, -45, 2200, 1000, 280, 750, 300),
        (2023, 1500, 700, 400, 300, 20, 320, -50, 2500, 1200, 250, 800, 280),
    ]:
        pe = date(year, 3, 31)
        _fin(db, company.id, "Total Revenue", Decimal(rev), pe)
        _fin(db, company.id, "Gross Profit", Decimal(gp), pe)
        _fin(db, company.id, "Operating Income", Decimal(oi), pe)
        _fin(db, company.id, "Net Income", Decimal(ni), pe)
        _fin(db, company.id, "Basic EPS", Decimal(eps), pe)
        _fin(db, company.id, "EBIT", Decimal(oi), pe)
        _fin(db, company.id, "Interest Expense", Decimal("-20"), pe)
        _fin(db, company.id, "Operating Cash Flow", Decimal(ocf), pe, "cashflow")
        _fin(db, company.id, "Capital Expenditure", Decimal(capex), pe, "cashflow")
        _fin(db, company.id, "Free Cash Flow", Decimal(ocf + capex), pe, "cashflow")
        _fin(db, company.id, "Total Assets", Decimal(assets), pe, "balance")
        _fin(db, company.id, "Stockholders Equity", Decimal(equity), pe, "balance")
        _fin(db, company.id, "Total Debt", Decimal(debt), pe, "balance")
        _fin(db, company.id, "Current Assets", Decimal(ca), pe, "balance")
        _fin(db, company.id, "Current Liabilities", Decimal(cl), pe, "balance")
        _fin(db, company.id, "Cash", Decimal(200), pe, "balance")
        _fin(db, company.id, "Inventory", Decimal(50), pe, "balance")
    # Stored TTM ratios
    for name, value in [
        ("trailing_pe", Decimal("18")),
        ("price_to_book", Decimal("3")),
        ("enterprise_to_ebitda", Decimal("12")),
        ("gross_margin", Decimal("0.45")),
        ("operating_margin", Decimal("0.25")),
        ("profit_margin", Decimal("0.18")),
        ("return_on_equity", Decimal("0.22")),
        ("return_on_assets", Decimal("0.12")),
        ("current_ratio", Decimal("2.5")),
        ("debt_to_equity", Decimal("0.3")),
    ]:
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name=name,
                metric_value=value,
                period_end=None,
                period_type="ttm",
                statement_type="ratio",
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    db.add(
        CompanyFundamentalInfo(
            company_id=company.id,
            business_summary="Test",
            currency="INR",
            market_cap=1_000_000_000,
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


class TestSectorRules:
    def test_banking_excludes_current_ratio(self):
        rules = resolve_sector_rules("Financial Services", "Banks—Regional")
        assert rules.profile == SectorProfile.BANKING
        assert "current_ratio" in rules.excluded_metrics
        assert "debt_to_equity" in rules.excluded_metrics

    def test_it_excludes_inventory(self):
        rules = resolve_sector_rules("Technology", "Software—Application")
        assert rules.profile == SectorProfile.IT
        assert "inventory_turnover" in rules.excluded_metrics

    def test_unknown_is_general(self):
        rules = resolve_sector_rules("Unknown Sector XYZ", None)
        assert rules.profile == SectorProfile.GENERAL
        assert "not sector-calibrated" in rules.label.lower()


class TestFundamentalAnalysis:
    def test_insufficient_data(self, db_session: Session, company: Company):
        result = analyze_fundamentals(db_session, company)
        assert result.overall_classification == Classification.INSUFFICIENT_DATA
        assert result.profitability.classification == Classification.INSUFFICIENT_DATA
        assert result.profitability.explanation

    def test_strong_profile_explainable(self, db_session: Session, company: Company):
        _seed_strong_company(db_session, company)
        result = analyze_fundamentals(db_session, company, current_price=Decimal("100"))
        assert result.profitability.classification != Classification.INSUFFICIENT_DATA
        assert result.profitability.metrics_used
        assert result.profitability.explanation
        assert result.growth.classification in {
            Classification.STRONG,
            Classification.HEALTHY,
            Classification.MODERATE,
        }
        assert result.analysis_version
        assert result.cash_flow_quality.classification != Classification.INSUFFICIENT_DATA

    def test_banking_sector_methodology(self, db_session: Session, company: Company):
        company.sector = "Financial Services"
        db_session.commit()
        _seed_strong_company(db_session, company)
        result = analyze_fundamentals(db_session, company, industry="Banks—Diversified")
        assert "Banking" in result.financial_stability.sector_methodology or "bank" in result.financial_stability.sector_methodology.lower()
        # Current ratio should be marked not applicable
        cr = next(m for m in result.financial_stability.metrics_used if m.key == "current_ratio")
        assert cr.applicable is False


class TestScoring:
    def test_weights_sum_to_one(self):
        assert sum(DIMENSION_WEIGHTS.values()) == Decimal("1.0")

    def test_insufficient_score_when_empty(self, db_session: Session, company: Company):
        analysis = analyze_fundamentals(db_session, company)
        score = score_from_analysis(analysis)
        assert score.score is None
        assert score.classification == Classification.INSUFFICIENT_DATA
        assert score.methodology_version == SCORING_VERSION
        assert "not redistributed" in score.explanation.lower() or "withheld" in score.explanation.lower()

    def test_score_with_data(self, db_session: Session, company: Company):
        _seed_strong_company(db_session, company)
        score = calculate_fundamental_score(db_session, company, current_price=Decimal("100"))
        assert score.score is not None
        assert Decimal("0") < score.score <= Decimal("100")
        assert score.metrics_evaluated >= MIN_DIMENSIONS_REQUIRED
        assert score.data_completeness > 0
        assert len(score.dimension_scores) == 5
        # Weights fixed even if some excluded
        for ds in score.dimension_scores:
            assert ds.weight == DIMENSION_WEIGHTS[ds.dimension]

    def test_missing_dimension_not_redistributed(self, db_session: Session, company: Company):
        # Only seed minimal profitability-ish without growth history beyond one year
        pe = date(2023, 3, 31)
        _fin(db_session, company.id, "Total Revenue", Decimal("1000"), pe)
        _fin(db_session, company.id, "Gross Profit", Decimal("400"), pe)
        _fin(db_session, company.id, "Operating Income", Decimal("200"), pe)
        _fin(db_session, company.id, "Net Income", Decimal("150"), pe)
        _fin(db_session, company.id, "Stockholders Equity", Decimal("800"), pe, "balance")
        _fin(db_session, company.id, "Total Assets", Decimal("2000"), pe, "balance")
        db_session.commit()
        score = calculate_fundamental_score(db_session, company)
        # Either withheld or score uses full weight base
        if score.score is not None:
            included_weight = sum(d.weight for d in score.dimension_scores if d.included)
            # completeness based on full weight
            assert score.data_completeness == (included_weight / Decimal("1") * 100).quantize(Decimal("0.01"))
        else:
            assert score.classification == Classification.INSUFFICIENT_DATA
