"""Tests for financial ratio calculation engine."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial
from app.services.financial_ratios import (
    FinancialRatio,
    calculate_all_ratios,
    calculate_asset_turnover,
    calculate_current_ratio,
    calculate_debt_to_equity,
    calculate_eps_growth,
    calculate_ev_ebitda,
    calculate_gross_margin,
    calculate_interest_coverage,
    calculate_inventory_turnover,
    calculate_net_margin,
    calculate_operating_margin,
    calculate_pb_ratio,
    calculate_pe_ratio,
    calculate_quick_ratio,
    calculate_revenue_growth,
    calculate_roa,
    calculate_roce,
    calculate_roe,
    get_metric_value,
    safe_divide,
    safe_multiply,
)


@pytest.fixture
def sample_company(db_session: Session) -> Company:
    """Create a sample company for testing."""
    company = Company(
        symbol="TEST",
        name="Test Company",
        provider_symbol="TEST.NS",
        exchange="NSE",
        instrument_type="EQUITY",  # Add required field
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def company_with_financials(db_session: Session, sample_company: Company) -> Company:
    """Create a company with complete financial data."""
    period_end = date(2023, 12, 31)
    retrieved = datetime.now()
    
    # Income statement data
    financials = [
        # Revenue and profitability
        ("Total Revenue", Decimal("1000000"), "income", "annual", period_end),
        ("Cost Of Revenue", Decimal("600000"), "income", "annual", period_end),
        ("Gross Profit", Decimal("400000"), "income", "annual", period_end),
        ("Operating Income", Decimal("200000"), "income", "annual", period_end),
        ("EBIT", Decimal("200000"), "income", "annual", period_end),
        ("EBITDA", Decimal("250000"), "income", "annual", period_end),
        ("Net Income", Decimal("150000"), "income", "annual", period_end),
        ("Interest Expense", Decimal("-20000"), "income", "annual", period_end),
        ("Basic EPS", Decimal("15"), "income", "annual", period_end),
        ("Diluted EPS", Decimal("14.5"), "income", "annual", period_end),
        
        # Balance sheet data
        ("Total Assets", Decimal("2000000"), "balance", "annual", period_end),
        ("Current Assets", Decimal("800000"), "balance", "annual", period_end),
        ("Cash", Decimal("200000"), "balance", "annual", period_end),
        ("Inventory", Decimal("150000"), "balance", "annual", period_end),
        ("Total Liabilities", Decimal("1200000"), "balance", "annual", period_end),
        ("Current Liabilities", Decimal("400000"), "balance", "annual", period_end),
        ("Total Debt", Decimal("500000"), "balance", "annual", period_end),
        ("Stockholders Equity", Decimal("800000"), "balance", "annual", period_end),
    ]
    
    for metric_name, value, stmt_type, period_type, pend in financials:
        financial = CompanyFinancial(
            company_id=sample_company.id,
            metric_name=metric_name,
            metric_value=value,
            statement_type=stmt_type,
            period_type=period_type,
            period_end=pend,
            retrieved_at=retrieved,
        )
        db_session.add(financial)
    
    db_session.commit()
    return sample_company


@pytest.fixture
def company_with_historical_data(db_session: Session, sample_company: Company) -> Company:
    """Create a company with historical financial data for growth calculations."""
    current_year = date(2023, 12, 31)
    previous_year = date(2022, 12, 31)
    retrieved = datetime.now()
    
    # Current year data
    current_data = [
        ("Total Revenue", Decimal("1000000"), "income", "annual", current_year),
        ("Basic EPS", Decimal("15"), "income", "annual", current_year),
    ]
    
    # Previous year data
    previous_data = [
        ("Total Revenue", Decimal("900000"), "income", "annual", previous_year),
        ("Basic EPS", Decimal("12"), "income", "annual", previous_year),
    ]
    
    for metric_name, value, stmt_type, period_type, pend in current_data + previous_data:
        financial = CompanyFinancial(
            company_id=sample_company.id,
            metric_name=metric_name,
            metric_value=value,
            statement_type=stmt_type,
            period_type=period_type,
            period_end=pend,
            retrieved_at=retrieved,
        )
        db_session.add(financial)
    
    db_session.commit()
    return sample_company


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_safe_divide_normal(self):
        """Test normal division."""
        result = safe_divide(Decimal("10"), Decimal("2"))
        assert result == Decimal("5")
    
    def test_safe_divide_none_numerator(self):
        """Test division with None numerator."""
        result = safe_divide(None, Decimal("2"))
        assert result is None
    
    def test_safe_divide_none_denominator(self):
        """Test division with None denominator."""
        result = safe_divide(Decimal("10"), None)
        assert result is None
    
    def test_safe_divide_zero_denominator(self):
        """Test division by zero."""
        result = safe_divide(Decimal("10"), Decimal("0"))
        assert result is None
    
    def test_safe_multiply_normal(self):
        """Test normal multiplication."""
        result = safe_multiply(Decimal("10"), Decimal("2"))
        assert result == Decimal("20")
    
    def test_safe_multiply_none(self):
        """Test multiplication with None."""
        result = safe_multiply(None, Decimal("2"))
        assert result is None


class TestMetricRetrieval:
    """Test metric retrieval functions."""
    
    def test_get_metric_value_exists(self, db_session: Session, company_with_financials: Company):
        """Test retrieving an existing metric."""
        revenue = get_metric_value(
            db_session,
            company_with_financials.id,
            "Total Revenue",
            "annual",
            "income",
        )
        assert revenue == Decimal("1000000")
    
    def test_get_metric_value_not_exists(self, db_session: Session, company_with_financials: Company):
        """Test retrieving a non-existent metric."""
        result = get_metric_value(
            db_session,
            company_with_financials.id,
            "Nonexistent Metric",
            "annual",
        )
        assert result is None
    
    def test_get_metric_value_latest(self, db_session: Session, sample_company: Company):
        """Test retrieving the latest metric when multiple exist."""
        # Add multiple records with different dates
        old_date = date(2022, 12, 31)
        new_date = date(2023, 12, 31)
        
        old_record = CompanyFinancial(
            company_id=sample_company.id,
            metric_name="Total Revenue",
            metric_value=Decimal("900000"),
            statement_type="income",
            period_type="annual",
            period_end=old_date,
            retrieved_at=datetime.now(),
        )
        
        new_record = CompanyFinancial(
            company_id=sample_company.id,
            metric_name="Total Revenue",
            metric_value=Decimal("1000000"),
            statement_type="income",
            period_type="annual",
            period_end=new_date,
            retrieved_at=datetime.now(),
        )
        
        db_session.add_all([old_record, new_record])
        db_session.commit()
        
        result = get_metric_value(
            db_session,
            sample_company.id,
            "Total Revenue",
            "annual",
            "income",
            latest=True,
        )
        
        assert result == Decimal("1000000")


class TestValuationRatios:
    """Test valuation ratio calculations."""
    
    def test_calculate_pe_ratio_success(self, db_session: Session, company_with_financials: Company):
        """Test successful P/E ratio calculation."""
        current_price = Decimal("300")
        result = calculate_pe_ratio(db_session, company_with_financials, current_price)
        
        assert result["name"] == "P/E Ratio"
        assert result["category"] == "valuation"
        assert result["inputs_available"] is True
        # EPS = 15, Price = 300, P/E = 20
        assert result["value"] == Decimal("20")
    
    def test_calculate_pe_ratio_no_price(self, db_session: Session, company_with_financials: Company):
        """Test P/E ratio without current price."""
        result = calculate_pe_ratio(db_session, company_with_financials, None)
        
        assert result["value"] is None
        assert result["inputs_available"] is False
        assert "price not available" in result["error"].lower()
    
    def test_calculate_pb_ratio_success(self, db_session: Session, company_with_financials: Company):
        """Test P/B ratio calculation with stored value."""
        # Add stored book value per share
        book_value = CompanyFinancial(
            company_id=company_with_financials.id,
            metric_name="book_value_per_share",
            metric_value=Decimal("80"),
            statement_type="ratio",
            period_type="ttm",
            period_end=date(2023, 12, 31),
            retrieved_at=datetime.now(),
        )
        db_session.add(book_value)
        db_session.commit()
        
        current_price = Decimal("300")
        result = calculate_pb_ratio(db_session, company_with_financials, current_price)
        
        assert result["inputs_available"] is True
        # Price = 300, Book Value = 80, P/B = 3.75
        assert result["value"] == Decimal("3.75")
    
    def test_calculate_ev_ebitda_success(self, db_session: Session, company_with_financials: Company):
        """Test EV/EBITDA calculation."""
        # Market cap = 3,000,000
        # Total Debt = 500,000
        # Cash = 200,000
        # EV = 3,000,000 + 500,000 - 200,000 = 3,300,000
        # EBITDA = 250,000
        # EV/EBITDA = 13.2
        
        market_cap = Decimal("3000000")
        result = calculate_ev_ebitda(db_session, company_with_financials, market_cap)
        
        assert result["inputs_available"] is True
        assert result["value"] == Decimal("13.2")


class TestProfitabilityRatios:
    """Test profitability ratio calculations."""
    
    def test_calculate_gross_margin(self, db_session: Session, company_with_financials: Company):
        """Test gross margin calculation."""
        result = calculate_gross_margin(db_session, company_with_financials)
        
        assert result["category"] == "profitability"
        assert result["inputs_available"] is True
        # Gross Profit = 400,000, Revenue = 1,000,000
        # Margin = 40%
        assert result["value"] == Decimal("40")
    
    def test_calculate_operating_margin(self, db_session: Session, company_with_financials: Company):
        """Test operating margin calculation."""
        result = calculate_operating_margin(db_session, company_with_financials)
        
        assert result["inputs_available"] is True
        # Operating Income = 200,000, Revenue = 1,000,000
        # Margin = 20%
        assert result["value"] == Decimal("20")
    
    def test_calculate_net_margin(self, db_session: Session, company_with_financials: Company):
        """Test net margin calculation."""
        result = calculate_net_margin(db_session, company_with_financials)
        
        assert result["inputs_available"] is True
        # Net Income = 150,000, Revenue = 1,000,000
        # Margin = 15%
        assert result["value"] == Decimal("15")
    
    def test_calculate_roe(self, db_session: Session, company_with_financials: Company):
        """Test ROE calculation."""
        result = calculate_roe(db_session, company_with_financials)
        
        assert result["category"] == "profitability"
        assert result["inputs_available"] is True
        # Net Income = 150,000, Equity = 800,000
        # ROE = 18.75%
        assert result["value"] == Decimal("18.75")
    
    def test_calculate_roa(self, db_session: Session, company_with_financials: Company):
        """Test ROA calculation."""
        result = calculate_roa(db_session, company_with_financials)
        
        assert result["inputs_available"] is True
        # Net Income = 150,000, Assets = 2,000,000
        # ROA = 7.5%
        assert result["value"] == Decimal("7.5")
    
    def test_calculate_roce(self, db_session: Session, company_with_financials: Company):
        """Test ROCE calculation."""
        result = calculate_roce(db_session, company_with_financials)
        
        assert result["category"] == "profitability"
        assert result["inputs_available"] is True
        # EBIT = 200,000
        # Capital Employed = Assets - Current Liabilities = 2,000,000 - 400,000 = 1,600,000
        # ROCE = 12.5%
        assert result["value"] == Decimal("12.5")


class TestLiquidityRatios:
    """Test liquidity ratio calculations."""
    
    def test_calculate_current_ratio(self, db_session: Session, company_with_financials: Company):
        """Test current ratio calculation."""
        result = calculate_current_ratio(db_session, company_with_financials)
        
        assert result["category"] == "liquidity"
        assert result["inputs_available"] is True
        # Current Assets = 800,000, Current Liabilities = 400,000
        # Ratio = 2.0
        assert result["value"] == Decimal("2")
    
    def test_calculate_quick_ratio(self, db_session: Session, company_with_financials: Company):
        """Test quick ratio calculation."""
        result = calculate_quick_ratio(db_session, company_with_financials)
        
        assert result["inputs_available"] is True
        # Current Assets = 800,000, Inventory = 150,000, Current Liabilities = 400,000
        # Quick Assets = 650,000
        # Ratio = 1.625
        assert result["value"] == Decimal("1.625")


class TestLeverageRatios:
    """Test leverage ratio calculations."""
    
    def test_calculate_debt_to_equity(self, db_session: Session, company_with_financials: Company):
        """Test debt-to-equity ratio calculation."""
        result = calculate_debt_to_equity(db_session, company_with_financials)
        
        assert result["category"] == "leverage"
        assert result["inputs_available"] is True
        # Total Debt = 500,000, Equity = 800,000
        # Ratio = 0.625
        assert result["value"] == Decimal("0.625")
    
    def test_calculate_interest_coverage(self, db_session: Session, company_with_financials: Company):
        """Test interest coverage ratio calculation."""
        result = calculate_interest_coverage(db_session, company_with_financials)
        
        assert result["category"] == "leverage"
        assert result["inputs_available"] is True
        # EBIT = 200,000, Interest Expense = 20,000 (absolute value)
        # Ratio = 10.0
        assert result["value"] == Decimal("10")


class TestEfficiencyRatios:
    """Test efficiency ratio calculations."""
    
    def test_calculate_asset_turnover(self, db_session: Session, company_with_financials: Company):
        """Test asset turnover calculation."""
        result = calculate_asset_turnover(db_session, company_with_financials)
        
        assert result["category"] == "efficiency"
        assert result["inputs_available"] is True
        # Revenue = 1,000,000, Assets = 2,000,000
        # Ratio = 0.5
        assert result["value"] == Decimal("0.5")
    
    def test_calculate_inventory_turnover(self, db_session: Session, company_with_financials: Company):
        """Test inventory turnover calculation."""
        result = calculate_inventory_turnover(db_session, company_with_financials)
        
        assert result["inputs_available"] is True
        # COGS = 600,000, Inventory = 150,000
        # Ratio = 4.0
        assert result["value"] == Decimal("4")


class TestGrowthMetrics:
    """Test growth metric calculations."""
    
    def test_calculate_revenue_growth(self, db_session: Session, company_with_historical_data: Company):
        """Test revenue growth calculation."""
        result = calculate_revenue_growth(db_session, company_with_historical_data)
        
        assert result["category"] == "growth"
        assert result["inputs_available"] is True
        # Current = 1,000,000, Previous = 900,000
        # Growth = 11.11%
        expected = Decimal("100000") / Decimal("900000") * Decimal("100")
        assert abs(result["value"] - expected) < Decimal("0.01")
    
    def test_calculate_eps_growth(self, db_session: Session, company_with_historical_data: Company):
        """Test EPS growth calculation."""
        result = calculate_eps_growth(db_session, company_with_historical_data)
        
        assert result["inputs_available"] is True
        # Current EPS = 15, Previous EPS = 12
        # Growth = 25%
        assert result["value"] == Decimal("25")
    
    def test_calculate_eps_growth_insufficient_data(self, db_session: Session, sample_company: Company):
        """Test EPS growth with insufficient historical data."""
        # Add only one year of data
        financial = CompanyFinancial(
            company_id=sample_company.id,
            metric_name="Basic EPS",
            metric_value=Decimal("15"),
            statement_type="income",
            period_type="annual",
            period_end=date(2023, 12, 31),
            retrieved_at=datetime.now(),
        )
        db_session.add(financial)
        db_session.commit()
        
        result = calculate_eps_growth(db_session, sample_company)
        
        assert result["value"] is None
        assert result["inputs_available"] is False
        assert "insufficient" in result["error"].lower()


class TestCalculateAllRatios:
    """Test comprehensive ratio calculation."""
    
    def test_calculate_all_ratios_complete_data(self, db_session: Session, company_with_financials: Company):
        """Test calculating all ratios with complete data."""
        current_price = Decimal("300")
        market_cap = Decimal("3000000")
        
        metrics = calculate_all_ratios(
            db_session,
            company_with_financials,
            current_price=current_price,
            market_cap=market_cap,
        )
        
        # Verify all categories present
        assert "valuation" in metrics
        assert "profitability" in metrics
        assert "liquidity" in metrics
        assert "leverage" in metrics
        assert "efficiency" in metrics
        assert "growth" in metrics
        
        # Verify some key ratios calculated
        assert "pe_ratio" in metrics["valuation"]
        assert "gross_margin" in metrics["profitability"]
        assert "current_ratio" in metrics["liquidity"]
        assert "debt_to_equity" in metrics["leverage"]
        assert "asset_turnover" in metrics["efficiency"]
        
        # Verify actual values
        assert metrics["profitability"]["gross_margin"]["value"] == Decimal("40")
        assert metrics["liquidity"]["current_ratio"]["value"] == Decimal("2")
    
    def test_calculate_all_ratios_missing_price(self, db_session: Session, company_with_financials: Company):
        """Test calculating ratios without price data."""
        metrics = calculate_all_ratios(db_session, company_with_financials)
        
        # Price-dependent ratios should be None
        assert metrics["valuation"]["pe_ratio"]["value"] is None
        
        # Other ratios should still calculate
        assert metrics["profitability"]["gross_margin"]["value"] is not None
        assert metrics["liquidity"]["current_ratio"]["value"] is not None


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_zero_denominator_handling(self, db_session: Session, sample_company: Company):
        """Test handling of zero denominators."""
        # Create data with zero equity
        financial = CompanyFinancial(
            company_id=sample_company.id,
            metric_name="Stockholders Equity",
            metric_value=Decimal("0"),
            statement_type="balance",
            period_type="annual",
            period_end=date(2023, 12, 31),
            retrieved_at=datetime.now(),
        )
        db_session.add(financial)
        db_session.commit()
        
        result = calculate_roe(db_session, sample_company)
        
        assert result["value"] is None
        assert result["inputs_available"] is False
    
    def test_negative_earnings_handling(self, db_session: Session, sample_company: Company):
        """Test handling of negative earnings."""
        # Add negative EPS
        financial = CompanyFinancial(
            company_id=sample_company.id,
            metric_name="Basic EPS",
            metric_value=Decimal("-5"),
            statement_type="income",
            period_type="annual",
            period_end=date(2023, 12, 31),
            retrieved_at=datetime.now(),
        )
        db_session.add(financial)
        db_session.commit()
        
        result = calculate_pe_ratio(db_session, sample_company, Decimal("100"))
        
        assert result["value"] is None
        assert "negative" in result["error"].lower()
    
    def test_missing_data_handling(self, db_session: Session, sample_company: Company):
        """Test handling of missing financial data."""
        result = calculate_gross_margin(db_session, sample_company)
        
        assert result["value"] is None
        assert result["inputs_available"] is False
        assert result["error"] is not None
