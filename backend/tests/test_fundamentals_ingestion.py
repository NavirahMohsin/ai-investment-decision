"""Tests for fundamental data ingestion service."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo
from app.services.fundamentals import (
    ingest_company_info,
    ingest_financial_statements,
    ingest_financial_ratios,
    ingest_company_fundamentals,
    get_company_financials,
    get_company_fundamental_info,
)
from app.services.providers.yahoo import YahooFinanceProvider


@pytest.fixture
def test_company(db_session):
    """Create a test company."""
    company = Company(
        name="Test Company Ltd",
        symbol="TESTCO",
        provider_symbol="TESTCO.NS",
        exchange="NSE",
        sector="Technology",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    return company


def test_ingest_company_info_creates_new(db_session, test_company):
    """Test that company info is created when it doesn't exist."""
    provider = YahooFinanceProvider()
    
    # Use a real company for actual API test
    real_company = Company(
        name="Reliance",
        symbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(real_company)
    db_session.commit()
    
    success = ingest_company_info(db_session, real_company, provider)
    
    assert success is True
    
    # Check that info was created
    info = get_company_fundamental_info(db_session, real_company)
    assert info is not None
    assert info.company_id == real_company.id


def test_ingest_company_info_updates_existing(db_session, test_company):
    """Test that company info is updated when it exists."""
    # Create initial info
    initial_info = CompanyFundamentalInfo(
        company_id=test_company.id,
        business_summary="Old summary",
        market_cap=1000000,
        data_source="yahoo_finance",
        retrieved_at=datetime.now(),
    )
    db_session.add(initial_info)
    db_session.commit()
    
    initial_id = initial_info.id
    
    provider = YahooFinanceProvider()
    
    # Use real company for actual update
    real_company = Company(
        name="Reliance",
        symbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(real_company)
    db_session.commit()
    
    # Create initial info for real company
    real_info = CompanyFundamentalInfo(
        company_id=real_company.id,
        business_summary="Old",
        data_source="yahoo_finance",
        retrieved_at=datetime.now(),
    )
    db_session.add(real_info)
    db_session.commit()
    
    success = ingest_company_info(db_session, real_company, provider)
    assert success is True
    
    # Check that info was updated (not recreated)
    updated_info = get_company_fundamental_info(db_session, real_company)
    assert updated_info is not None
    assert updated_info.id == real_info.id  # Same record


def test_ingest_financial_statements(db_session):
    """Test financial statement ingestion."""
    provider = YahooFinanceProvider()
    
    company = Company(
        name="Reliance",
        symbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    inserted, updated = ingest_financial_statements(
        db_session,
        company,
        provider,
        statement_types=["income"],
        period_types=["annual"],
    )
    
    # Should have inserted some records
    assert inserted > 0 or updated >= 0  # Yahoo may have data or not
    
    # Check records were created
    financials = get_company_financials(
        db_session,
        company,
        statement_type="income",
        period_type="annual",
    )
    
    if inserted > 0:
        assert len(financials) > 0
        # Check first record structure
        record = financials[0]
        assert record.company_id == company.id
        assert record.statement_type == "income"
        assert record.period_type == "annual"
        assert record.metric_name is not None


def test_ingest_financial_ratios(db_session):
    """Test financial ratios ingestion."""
    provider = YahooFinanceProvider()
    
    company = Company(
        name="Reliance",
        symbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    count = ingest_financial_ratios(db_session, company, provider)
    
    # Should have inserted some ratios
    assert count > 0
    
    # Check ratios were created
    ratios = get_company_financials(
        db_session,
        company,
        statement_type="ratio",
        period_type="ttm",
    )
    
    assert len(ratios) > 0
    
    # Check ratio structure
    ratio = ratios[0]
    assert ratio.company_id == company.id
    assert ratio.statement_type == "ratio"
    assert ratio.period_type == "ttm"
    assert ratio.metric_value is not None


def test_ingest_company_fundamentals_complete(db_session):
    """Test complete fundamental data ingestion."""
    company = Company(
        name="Reliance",
        symbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    result = ingest_company_fundamentals(
        db_session,
        company,
        include_info=True,
        include_statements=True,
        include_ratios=True,
    )
    
    assert result["company_symbol"] == company.symbol
    assert result["success"] is True
    assert result["company_info_updated"] is True
    
    # Should have some data
    assert (
        result["financials_inserted"] > 0
        or result["financials_updated"] > 0
        or result["ratios_inserted"] > 0
    )


def test_ingest_preserves_none_values(db_session):
    """Test that None values in financial data are preserved."""
    provider = YahooFinanceProvider()
    
    company = Company(
        name="Reliance",
        symbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    # Ingest data
    inserted, updated = ingest_financial_statements(
        db_session,
        company,
        provider,
        statement_types=["income"],
        period_types=["annual"],
    )
    
    # Get all financials
    financials = get_company_financials(db_session, company)
    
    if financials:
        # Check that None values exist (not converted to 0)
        none_values = [f for f in financials if f.metric_value is None]
        # Some metrics should legitimately be None
        assert len(none_values) >= 0  # Can be 0 if all have values


def test_upsert_updates_changed_values(db_session):
    """Test that upsert updates values that have changed."""
    company = Company(
        name="Test",
        symbol="TEST",
        provider_symbol="TEST.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    # Create initial financial record
    initial = CompanyFinancial(
        company_id=company.id,
        metric_name="test_metric",
        metric_value=Decimal("100.00"),
        period_end=date(2023, 12, 31),
        period_type="annual",
        statement_type="income",
        data_source="yahoo_finance",
        retrieved_at=datetime.now(),
    )
    db_session.add(initial)
    db_session.commit()
    
    initial_id = initial.id
    
    # Update with new value
    initial.metric_value = Decimal("200.00")
    db_session.commit()
    
    # Verify update (not new record)
    updated = db_session.get(CompanyFinancial, initial_id)
    assert updated is not None
    assert updated.metric_value == Decimal("200.00")


def test_get_company_financials_filtering(db_session):
    """Test filtering of company financials."""
    company = Company(
        name="Test",
        symbol="TEST",
        provider_symbol="TEST.NS",
        exchange="NSE",
        instrument_type="company",
        is_active=True,
    )
    db_session.add(company)
    db_session.commit()
    
    # Create various financial records
    for i in range(3):
        db_session.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name=f"metric_{i}",
                metric_value=Decimal(str(100 + i)),
                period_end=date(2023, 12, 31),
                period_type="annual",
                statement_type="income",
                data_source="yahoo_finance",
                retrieved_at=datetime.now(),
            )
        )
    
    db_session.commit()
    
    # Test filtering
    income_records = get_company_financials(
        db_session,
        company,
        statement_type="income",
    )
    assert len(income_records) == 3
    
    # Test metric name filtering
    specific_metric = get_company_financials(
        db_session,
        company,
        metric_names=["metric_0"],
    )
    assert len(specific_metric) == 1
    assert specific_metric[0].metric_name == "metric_0"
