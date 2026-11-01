"""Financial ratio and valuation calculation engine."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo


class FinancialRatio(TypedDict, total=False):
    """Calculated financial ratio."""
    name: str
    value: Decimal | None
    category: str  # 'valuation', 'profitability', 'liquidity', 'leverage', 'efficiency', 'growth'
    calculation_date: date | None
    inputs_available: bool
    error: str | None


class FinancialMetrics(TypedDict, total=False):
    """Collection of financial metrics for a company."""
    valuation: dict[str, FinancialRatio]
    profitability: dict[str, FinancialRatio]
    liquidity: dict[str, FinancialRatio]
    leverage: dict[str, FinancialRatio]
    efficiency: dict[str, FinancialRatio]
    growth: dict[str, FinancialRatio]


def safe_divide(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    """
    Safely divide two values, handling None and zero.
    
    Returns:
        Result of division or None if not possible
    """
    if numerator is None or denominator is None:
        return None
    
    if denominator == 0:
        return None
    
    try:
        return numerator / denominator
    except:
        return None


def safe_multiply(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    """Safely multiply two values."""
    if a is None or b is None:
        return None
    try:
        return a * b
    except:
        return None


def get_metric_value(
    db: Session,
    company_id: int,
    metric_name: str,
    period_type: str = "annual",
    statement_type: str | None = None,
    latest: bool = True,
) -> Decimal | None:
    """
    Get a specific financial metric value for a company.
    
    Args:
        db: Database session
        company_id: Company ID
        metric_name: Name of the metric
        period_type: Period type (annual, quarterly, ttm)
        statement_type: Statement type filter
        latest: If True, get most recent value
    
    Returns:
        Metric value or None
    """
    query = select(CompanyFinancial).where(
        CompanyFinancial.company_id == company_id,
        CompanyFinancial.metric_name == metric_name,
        CompanyFinancial.period_type == period_type,
    )
    
    if statement_type:
        query = query.where(CompanyFinancial.statement_type == statement_type)
    
    if latest:
        query = query.order_by(
            CompanyFinancial.period_end.desc().nullslast(),
            CompanyFinancial.retrieved_at.desc(),
        ).limit(1)
    
    record = db.scalar(query)
    return record.metric_value if record else None


def calculate_pe_ratio(
    db: Session,
    company: Company,
    current_price: Decimal | None = None,
) -> FinancialRatio:
    """
    Calculate Price-to-Earnings (P/E) ratio.
    
    P/E = Market Price per Share / Earnings per Share
    """
    # Try to get from stored ratios first
    stored_pe = get_metric_value(db, company.id, "trailing_pe", "ttm", "ratio")
    
    if stored_pe:
        return FinancialRatio(
            name="P/E Ratio (Trailing)",
            value=stored_pe,
            category="valuation",
            inputs_available=True,
        )
    
    # Calculate if we have current price and EPS
    if current_price is None:
        return FinancialRatio(
            name="P/E Ratio",
            value=None,
            category="valuation",
            inputs_available=False,
            error="Current price not available",
        )
    
    eps = get_metric_value(db, company.id, "Basic EPS", "annual", "income")
    
    if eps is None:
        eps = get_metric_value(db, company.id, "Diluted EPS", "annual", "income")
    
    if eps is None or eps <= 0:
        return FinancialRatio(
            name="P/E Ratio",
            value=None,
            category="valuation",
            inputs_available=False,
            error="EPS not available or negative",
        )
    
    pe_ratio = safe_divide(current_price, eps)
    
    return FinancialRatio(
        name="P/E Ratio",
        value=pe_ratio,
        category="valuation",
        inputs_available=True,
    )


def calculate_pb_ratio(
    db: Session,
    company: Company,
    current_price: Decimal | None = None,
) -> FinancialRatio:
    """
    Calculate Price-to-Book (P/B) ratio.
    
    P/B = Market Price per Share / Book Value per Share
    """
    # Try stored ratio first
    stored_pb = get_metric_value(db, company.id, "price_to_book", "ttm", "ratio")
    
    if stored_pb:
        return FinancialRatio(
            name="P/B Ratio",
            value=stored_pb,
            category="valuation",
            inputs_available=True,
        )
    
    # Calculate if needed
    if current_price is None:
        return FinancialRatio(
            name="P/B Ratio",
            value=None,
            category="valuation",
            inputs_available=False,
            error="Current price not available",
        )
    
    # Get total equity and shares outstanding
    equity = get_metric_value(db, company.id, "Stockholders Equity", "annual", "balance")
    
    if equity is None or equity <= 0:
        return FinancialRatio(
            name="P/B Ratio",
            value=None,
            category="valuation",
            inputs_available=False,
            error="Equity not available or negative",
        )
    
    # For simplified calculation, use stored book value per share if available
    book_value_per_share = get_metric_value(db, company.id, "book_value_per_share", "ttm", "ratio")
    
    if book_value_per_share and book_value_per_share > 0:
        pb_ratio = safe_divide(current_price, book_value_per_share)
        return FinancialRatio(
            name="P/B Ratio",
            value=pb_ratio,
            category="valuation",
            inputs_available=True,
        )
    
    return FinancialRatio(
        name="P/B Ratio",
        value=None,
        category="valuation",
        inputs_available=False,
        error="Book value per share not available",
    )


def calculate_gross_margin(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Gross Profit Margin.
    
    Gross Margin = (Gross Profit / Total Revenue) × 100
    """
    # Try stored margin first
    stored_margin = get_metric_value(db, company.id, "gross_margin", "ttm", "ratio")
    
    if stored_margin:
        return FinancialRatio(
            name="Gross Margin",
            value=stored_margin * 100 if stored_margin else None,  # Convert to percentage
            category="profitability",
            inputs_available=True,
        )
    
    # Calculate from financial statements
    gross_profit = get_metric_value(db, company.id, "Gross Profit", "annual", "income")
    revenue = get_metric_value(db, company.id, "Total Revenue", "annual", "income")
    
    if gross_profit is None or revenue is None or revenue == 0:
        return FinancialRatio(
            name="Gross Margin",
            value=None,
            category="profitability",
            inputs_available=False,
            error="Gross profit or revenue not available",
        )
    
    margin = safe_divide(gross_profit, revenue)
    margin_pct = safe_multiply(margin, Decimal("100")) if margin else None
    
    return FinancialRatio(
        name="Gross Margin",
        value=margin_pct,
        category="profitability",
        inputs_available=True,
    )


def calculate_operating_margin(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Operating Profit Margin.
    
    Operating Margin = (Operating Income / Total Revenue) × 100
    """
    # Try stored margin
    stored_margin = get_metric_value(db, company.id, "operating_margin", "ttm", "ratio")
    
    if stored_margin:
        return FinancialRatio(
            name="Operating Margin",
            value=stored_margin * 100 if stored_margin else None,
            category="profitability",
            inputs_available=True,
        )
    
    operating_income = get_metric_value(db, company.id, "Operating Income", "annual", "income")
    revenue = get_metric_value(db, company.id, "Total Revenue", "annual", "income")
    
    if operating_income is None or revenue is None or revenue == 0:
        return FinancialRatio(
            name="Operating Margin",
            value=None,
            category="profitability",
            inputs_available=False,
            error="Operating income or revenue not available",
        )
    
    margin = safe_divide(operating_income, revenue)
    margin_pct = safe_multiply(margin, Decimal("100")) if margin else None
    
    return FinancialRatio(
        name="Operating Margin",
        value=margin_pct,
        category="profitability",
        inputs_available=True,
    )


def calculate_net_margin(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Net Profit Margin.
    
    Net Margin = (Net Income / Total Revenue) × 100
    """
    # Try stored margin
    stored_margin = get_metric_value(db, company.id, "profit_margin", "ttm", "ratio")
    
    if stored_margin:
        return FinancialRatio(
            name="Net Margin",
            value=stored_margin * 100 if stored_margin else None,
            category="profitability",
            inputs_available=True,
        )
    
    net_income = get_metric_value(db, company.id, "Net Income", "annual", "income")
    revenue = get_metric_value(db, company.id, "Total Revenue", "annual", "income")
    
    if net_income is None or revenue is None or revenue == 0:
        return FinancialRatio(
            name="Net Margin",
            value=None,
            category="profitability",
            inputs_available=False,
            error="Net income or revenue not available",
        )
    
    margin = safe_divide(net_income, revenue)
    margin_pct = safe_multiply(margin, Decimal("100")) if margin else None
    
    return FinancialRatio(
        name="Net Margin",
        value=margin_pct,
        category="profitability",
        inputs_available=True,
    )


def calculate_roe(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Return on Equity (ROE).
    
    ROE = (Net Income / Shareholders' Equity) × 100
    """
    # Try stored ROE
    stored_roe = get_metric_value(db, company.id, "return_on_equity", "ttm", "ratio")
    
    if stored_roe:
        return FinancialRatio(
            name="ROE",
            value=stored_roe * 100 if stored_roe else None,
            category="profitability",
            inputs_available=True,
        )
    
    net_income = get_metric_value(db, company.id, "Net Income", "annual", "income")
    equity = get_metric_value(db, company.id, "Stockholders Equity", "annual", "balance")
    
    if net_income is None or equity is None or equity == 0:
        return FinancialRatio(
            name="ROE",
            value=None,
            category="profitability",
            inputs_available=False,
            error="Net income or equity not available or zero",
        )
    
    roe = safe_divide(net_income, equity)
    roe_pct = safe_multiply(roe, Decimal("100")) if roe else None
    
    return FinancialRatio(
        name="ROE",
        value=roe_pct,
        category="profitability",
        inputs_available=True,
    )


def calculate_roa(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Return on Assets (ROA).
    
    ROA = (Net Income / Total Assets) × 100
    """
    # Try stored ROA
    stored_roa = get_metric_value(db, company.id, "return_on_assets", "ttm", "ratio")
    
    if stored_roa:
        return FinancialRatio(
            name="ROA",
            value=stored_roa * 100 if stored_roa else None,
            category="profitability",
            inputs_available=True,
        )
    
    net_income = get_metric_value(db, company.id, "Net Income", "annual", "income")
    assets = get_metric_value(db, company.id, "Total Assets", "annual", "balance")
    
    if net_income is None or assets is None or assets == 0:
        return FinancialRatio(
            name="ROA",
            value=None,
            category="profitability",
            inputs_available=False,
            error="Net income or assets not available or zero",
        )
    
    roa = safe_divide(net_income, assets)
    roa_pct = safe_multiply(roa, Decimal("100")) if roa else None
    
    return FinancialRatio(
        name="ROA",
        value=roa_pct,
        category="profitability",
        inputs_available=True,
    )


def calculate_current_ratio(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Current Ratio.
    
    Current Ratio = Current Assets / Current Liabilities
    """
    # Try stored ratio
    stored_ratio = get_metric_value(db, company.id, "current_ratio", "ttm", "ratio")
    
    if stored_ratio:
        return FinancialRatio(
            name="Current Ratio",
            value=stored_ratio,
            category="liquidity",
            inputs_available=True,
        )
    
    current_assets = get_metric_value(db, company.id, "Current Assets", "annual", "balance")
    current_liabilities = get_metric_value(db, company.id, "Current Liabilities", "annual", "balance")
    
    if current_assets is None or current_liabilities is None or current_liabilities == 0:
        return FinancialRatio(
            name="Current Ratio",
            value=None,
            category="liquidity",
            inputs_available=False,
            error="Current assets or liabilities not available",
        )
    
    ratio = safe_divide(current_assets, current_liabilities)
    
    return FinancialRatio(
        name="Current Ratio",
        value=ratio,
        category="liquidity",
        inputs_available=True,
    )


def calculate_quick_ratio(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Quick Ratio (Acid Test).
    
    Quick Ratio = (Current Assets - Inventory) / Current Liabilities
    """
    # Try stored ratio
    stored_ratio = get_metric_value(db, company.id, "quick_ratio", "ttm", "ratio")
    
    if stored_ratio:
        return FinancialRatio(
            name="Quick Ratio",
            value=stored_ratio,
            category="liquidity",
            inputs_available=True,
        )
    
    current_assets = get_metric_value(db, company.id, "Current Assets", "annual", "balance")
    inventory = get_metric_value(db, company.id, "Inventory", "annual", "balance") or Decimal("0")
    current_liabilities = get_metric_value(db, company.id, "Current Liabilities", "annual", "balance")
    
    if current_assets is None or current_liabilities is None or current_liabilities == 0:
        return FinancialRatio(
            name="Quick Ratio",
            value=None,
            category="liquidity",
            inputs_available=False,
            error="Current assets or liabilities not available",
        )
    
    quick_assets = current_assets - inventory
    ratio = safe_divide(quick_assets, current_liabilities)
    
    return FinancialRatio(
        name="Quick Ratio",
        value=ratio,
        category="liquidity",
        inputs_available=True,
    )


def calculate_debt_to_equity(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Debt-to-Equity Ratio.
    
    D/E = Total Debt / Shareholders' Equity
    """
    # Try stored ratio
    stored_ratio = get_metric_value(db, company.id, "debt_to_equity", "ttm", "ratio")
    
    if stored_ratio:
        return FinancialRatio(
            name="Debt-to-Equity",
            value=stored_ratio,
            category="leverage",
            inputs_available=True,
        )
    
    total_debt = get_metric_value(db, company.id, "total_debt", "ttm", "ratio")
    
    if total_debt is None:
        # Try to calculate from balance sheet
        total_debt = get_metric_value(db, company.id, "Total Debt", "annual", "balance")
    
    equity = get_metric_value(db, company.id, "Stockholders Equity", "annual", "balance")
    
    if total_debt is None or equity is None or equity == 0:
        return FinancialRatio(
            name="Debt-to-Equity",
            value=None,
            category="leverage",
            inputs_available=False,
            error="Total debt or equity not available",
        )
    
    ratio = safe_divide(total_debt, equity)
    
    return FinancialRatio(
        name="Debt-to-Equity",
        value=ratio,
        category="leverage",
        inputs_available=True,
    )


def calculate_interest_coverage(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Interest Coverage Ratio.
    
    Interest Coverage = EBIT / Interest Expense
    """
    ebit = get_metric_value(db, company.id, "EBIT", "annual", "income")
    
    if ebit is None:
        # Try calculating from Operating Income
        ebit = get_metric_value(db, company.id, "Operating Income", "annual", "income")
    
    interest_expense = get_metric_value(db, company.id, "Interest Expense", "annual", "income")
    
    if ebit is None or interest_expense is None or interest_expense == 0:
        return FinancialRatio(
            name="Interest Coverage",
            value=None,
            category="leverage",
            inputs_available=False,
            error="EBIT or interest expense not available",
        )
    
    ratio = safe_divide(ebit, abs(interest_expense))  # Interest expense is typically negative
    
    return FinancialRatio(
        name="Interest Coverage",
        value=ratio,
        category="leverage",
        inputs_available=True,
    )


def calculate_roce(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Return on Capital Employed (ROCE).
    
    ROCE = EBIT / (Total Assets - Current Liabilities) × 100
    """
    ebit = get_metric_value(db, company.id, "EBIT", "annual", "income")
    
    if ebit is None:
        ebit = get_metric_value(db, company.id, "Operating Income", "annual", "income")
    
    total_assets = get_metric_value(db, company.id, "Total Assets", "annual", "balance")
    current_liabilities = get_metric_value(db, company.id, "Current Liabilities", "annual", "balance")
    
    if ebit is None or total_assets is None or current_liabilities is None:
        return FinancialRatio(
            name="ROCE",
            value=None,
            category="profitability",
            inputs_available=False,
            error="EBIT, assets, or liabilities not available",
        )
    
    capital_employed = total_assets - current_liabilities
    
    if capital_employed == 0:
        return FinancialRatio(
            name="ROCE",
            value=None,
            category="profitability",
            inputs_available=False,
            error="Capital employed is zero",
        )
    
    roce = safe_divide(ebit, capital_employed)
    roce_pct = safe_multiply(roce, Decimal("100")) if roce else None
    
    return FinancialRatio(
        name="ROCE",
        value=roce_pct,
        category="profitability",
        inputs_available=True,
    )


def calculate_asset_turnover(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Asset Turnover Ratio.
    
    Asset Turnover = Total Revenue / Average Total Assets
    """
    revenue = get_metric_value(db, company.id, "Total Revenue", "annual", "income")
    total_assets = get_metric_value(db, company.id, "Total Assets", "annual", "balance")
    
    if revenue is None or total_assets is None or total_assets == 0:
        return FinancialRatio(
            name="Asset Turnover",
            value=None,
            category="efficiency",
            inputs_available=False,
            error="Revenue or assets not available",
        )
    
    ratio = safe_divide(revenue, total_assets)
    
    return FinancialRatio(
        name="Asset Turnover",
        value=ratio,
        category="efficiency",
        inputs_available=True,
    )


def calculate_inventory_turnover(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Inventory Turnover Ratio.
    
    Inventory Turnover = Cost of Revenue / Average Inventory
    """
    cogs = get_metric_value(db, company.id, "Cost Of Revenue", "annual", "income")
    inventory = get_metric_value(db, company.id, "Inventory", "annual", "balance")
    
    if cogs is None or inventory is None or inventory == 0:
        return FinancialRatio(
            name="Inventory Turnover",
            value=None,
            category="efficiency",
            inputs_available=False,
            error="COGS or inventory not available",
        )
    
    ratio = safe_divide(cogs, inventory)
    
    return FinancialRatio(
        name="Inventory Turnover",
        value=ratio,
        category="efficiency",
        inputs_available=True,
    )


def calculate_revenue_growth(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Year-over-Year Revenue Growth.
    
    Revenue Growth = ((Current Revenue - Previous Revenue) / Previous Revenue) × 100
    """
    # Get two most recent annual revenue figures
    query = select(CompanyFinancial).where(
        CompanyFinancial.company_id == company.id,
        CompanyFinancial.metric_name == "Total Revenue",
        CompanyFinancial.period_type == "annual",
        CompanyFinancial.statement_type == "income",
    ).order_by(CompanyFinancial.period_end.desc().nullslast()).limit(2)
    
    records = list(db.execute(query).scalars())
    
    if len(records) < 2:
        return FinancialRatio(
            name="Revenue Growth YoY",
            value=None,
            category="growth",
            inputs_available=False,
            error="Insufficient historical data",
        )
    
    current_revenue = records[0].metric_value
    previous_revenue = records[1].metric_value
    
    if current_revenue is None or previous_revenue is None or previous_revenue == 0:
        return FinancialRatio(
            name="Revenue Growth YoY",
            value=None,
            category="growth",
            inputs_available=False,
            error="Revenue data incomplete",
        )
    
    growth = safe_divide(current_revenue - previous_revenue, previous_revenue)
    growth_pct = safe_multiply(growth, Decimal("100")) if growth else None
    
    return FinancialRatio(
        name="Revenue Growth YoY",
        value=growth_pct,
        category="growth",
        inputs_available=True,
    )


def calculate_eps_growth(db: Session, company: Company) -> FinancialRatio:
    """
    Calculate Year-over-Year EPS Growth.
    
    EPS Growth = ((Current EPS - Previous EPS) / Previous EPS) × 100
    """
    # Get two most recent annual EPS figures
    query = select(CompanyFinancial).where(
        CompanyFinancial.company_id == company.id,
        CompanyFinancial.metric_name == "Basic EPS",
        CompanyFinancial.period_type == "annual",
        CompanyFinancial.statement_type == "income",
    ).order_by(CompanyFinancial.period_end.desc().nullslast()).limit(2)
    
    records = list(db.execute(query).scalars())
    
    if len(records) < 2:
        # Try Diluted EPS if Basic EPS not available
        query = select(CompanyFinancial).where(
            CompanyFinancial.company_id == company.id,
            CompanyFinancial.metric_name == "Diluted EPS",
            CompanyFinancial.period_type == "annual",
            CompanyFinancial.statement_type == "income",
        ).order_by(CompanyFinancial.period_end.desc().nullslast()).limit(2)
        
        records = list(db.execute(query).scalars())
    
    if len(records) < 2:
        return FinancialRatio(
            name="EPS Growth YoY",
            value=None,
            category="growth",
            inputs_available=False,
            error="Insufficient historical data",
        )
    
    current_eps = records[0].metric_value
    previous_eps = records[1].metric_value
    
    if current_eps is None or previous_eps is None:
        return FinancialRatio(
            name="EPS Growth YoY",
            value=None,
            category="growth",
            inputs_available=False,
            error="EPS data incomplete",
        )
    
    # Handle negative EPS (loss) scenarios
    if previous_eps <= 0:
        return FinancialRatio(
            name="EPS Growth YoY",
            value=None,
            category="growth",
            inputs_available=False,
            error="Previous EPS was negative or zero",
        )
    
    growth = safe_divide(current_eps - previous_eps, previous_eps)
    growth_pct = safe_multiply(growth, Decimal("100")) if growth else None
    
    return FinancialRatio(
        name="EPS Growth YoY",
        value=growth_pct,
        category="growth",
        inputs_available=True,
    )


def calculate_ev_ebitda(
    db: Session,
    company: Company,
    market_cap: Decimal | None = None,
) -> FinancialRatio:
    """
    Calculate EV/EBITDA Ratio.
    
    EV/EBITDA = Enterprise Value / EBITDA
    Enterprise Value = Market Cap + Total Debt - Cash
    """
    # Try stored ratio first
    stored_ratio = get_metric_value(db, company.id, "enterprise_to_ebitda", "ttm", "ratio")
    
    if stored_ratio:
        return FinancialRatio(
            name="EV/EBITDA",
            value=stored_ratio,
            category="valuation",
            inputs_available=True,
        )
    
    # Calculate if we have the components
    if market_cap is None:
        return FinancialRatio(
            name="EV/EBITDA",
            value=None,
            category="valuation",
            inputs_available=False,
            error="Market cap not available",
        )
    
    # Get EBITDA
    ebitda = get_metric_value(db, company.id, "EBITDA", "annual", "income")
    
    if ebitda is None or ebitda == 0:
        return FinancialRatio(
            name="EV/EBITDA",
            value=None,
            category="valuation",
            inputs_available=False,
            error="EBITDA not available or zero",
        )
    
    # Get debt and cash
    total_debt = get_metric_value(db, company.id, "Total Debt", "annual", "balance") or Decimal("0")
    cash = get_metric_value(db, company.id, "Cash", "annual", "balance") or Decimal("0")
    
    # Calculate EV
    enterprise_value = market_cap + total_debt - cash
    
    ratio = safe_divide(enterprise_value, ebitda)
    
    return FinancialRatio(
        name="EV/EBITDA",
        value=ratio,
        category="valuation",
        inputs_available=True,
    )


def calculate_all_ratios(
    db: Session,
    company: Company,
    current_price: Decimal | None = None,
    market_cap: Decimal | None = None,
    period_type: str = "annual",
) -> FinancialMetrics:
    """
    Calculate all available financial ratios for a company.
    
    Args:
        db: Database session
        company: Company model instance
        current_price: Current market price (optional, for valuation ratios)
        market_cap: Market capitalization (optional, for EV/EBITDA)
        period_type: Period type to use ('annual', 'quarterly', 'ttm')
    
    Returns:
        FinancialMetrics with all calculated ratios
    """
    metrics: FinancialMetrics = {
        "valuation": {},
        "profitability": {},
        "liquidity": {},
        "leverage": {},
        "efficiency": {},
        "growth": {},
    }
    
    # Valuation ratios
    metrics["valuation"]["pe_ratio"] = calculate_pe_ratio(db, company, current_price)
    metrics["valuation"]["pb_ratio"] = calculate_pb_ratio(db, company, current_price)
    metrics["valuation"]["ev_ebitda"] = calculate_ev_ebitda(db, company, market_cap)
    
    # Profitability ratios
    metrics["profitability"]["gross_margin"] = calculate_gross_margin(db, company)
    metrics["profitability"]["operating_margin"] = calculate_operating_margin(db, company)
    metrics["profitability"]["net_margin"] = calculate_net_margin(db, company)
    metrics["profitability"]["roe"] = calculate_roe(db, company)
    metrics["profitability"]["roa"] = calculate_roa(db, company)
    metrics["profitability"]["roce"] = calculate_roce(db, company)
    
    # Liquidity ratios
    metrics["liquidity"]["current_ratio"] = calculate_current_ratio(db, company)
    metrics["liquidity"]["quick_ratio"] = calculate_quick_ratio(db, company)
    
    # Leverage ratios
    metrics["leverage"]["debt_to_equity"] = calculate_debt_to_equity(db, company)
    metrics["leverage"]["interest_coverage"] = calculate_interest_coverage(db, company)
    
    # Efficiency ratios
    metrics["efficiency"]["asset_turnover"] = calculate_asset_turnover(db, company)
    metrics["efficiency"]["inventory_turnover"] = calculate_inventory_turnover(db, company)
    
    # Growth metrics
    metrics["growth"]["revenue_growth"] = calculate_revenue_growth(db, company)
    metrics["growth"]["eps_growth"] = calculate_eps_growth(db, company)
    
    return metrics
