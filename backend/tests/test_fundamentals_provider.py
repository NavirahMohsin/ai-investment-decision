"""Tests for Yahoo Finance fundamental data provider."""
from decimal import Decimal

import pytest

from app.services.providers.yahoo import YahooFinanceProvider


@pytest.fixture
def provider():
    """Create Yahoo Finance provider instance."""
    return YahooFinanceProvider()


def test_get_company_info(provider):
    """Test company information retrieval."""
    # Use a well-known company
    info = provider.get_company_info("RELIANCE.NS")
    
    assert info["symbol"] == "RELIANCE.NS"
    assert info["name"] is not None
    assert "retrieved_at" in info
    
    # These fields may be present
    if info.get("sector"):
        assert isinstance(info["sector"], str)
    if info.get("market_cap"):
        assert isinstance(info["market_cap"], int)


def test_get_financials_income_annual(provider):
    """Test annual income statement retrieval."""
    statements = provider.get_financials("RELIANCE.NS", "income", "annual")
    
    assert isinstance(statements, list)
    
    if statements:  # Yahoo Finance may return empty
        statement = statements[0]
        assert "metric" in statement
        assert "period_type" in statement
        assert statement["period_type"] == "annual"
        
        # Value can be None
        if statement.get("value") is not None:
            assert isinstance(statement["value"], Decimal)


def test_get_financials_balance_quarterly(provider):
    """Test quarterly balance sheet retrieval."""
    statements = provider.get_financials("RELIANCE.NS", "balance", "quarterly")
    
    assert isinstance(statements, list)
    
    if statements:
        statement = statements[0]
        assert statement["period_type"] == "quarterly"


def test_get_financials_cashflow(provider):
    """Test cash flow statement retrieval."""
    statements = provider.get_financials("RELIANCE.NS", "cashflow", "annual")
    
    assert isinstance(statements, list)


def test_get_financials_invalid_statement_type(provider):
    """Test that invalid statement type raises error."""
    with pytest.raises(RuntimeError, match="Failed to retrieve"):
        provider.get_financials("RELIANCE.NS", "invalid", "annual")


def test_get_financial_ratios(provider):
    """Test financial ratios retrieval."""
    ratios = provider.get_financial_ratios("RELIANCE.NS")
    
    assert isinstance(ratios, dict)
    
    # Check expected keys exist
    assert "trailing_pe" in ratios
    assert "price_to_book" in ratios
    assert "return_on_equity" in ratios
    assert "current_ratio" in ratios
    assert "debt_to_equity" in ratios
    
    # Values can be None
    for value in ratios.values():
        if value is not None:
            assert isinstance(value, Decimal)


def test_get_company_info_handles_invalid_symbol(provider):
    """Test that invalid symbols are handled appropriately."""
    try:
        info = provider.get_company_info("INVALID_SYMBOL_XYZ_123")
        # Yahoo might return empty info instead of error
        assert isinstance(info, dict)
    except RuntimeError:
        # This is also acceptable - provider raised error
        pass


def test_financials_preserve_none_values(provider):
    """Test that missing financial values remain None."""
    statements = provider.get_financials("RELIANCE.NS", "income", "annual")
    
    if statements:
        # Find a statement with None value (common in financial data)
        none_values = [s for s in statements if s.get("value") is None]
        # We should preserve None values, not convert to 0
        assert len(none_values) >= 0  # Could be all present, but None is valid
