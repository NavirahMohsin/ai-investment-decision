from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import TypedDict

import yfinance as yf
import pandas as pd

from app.services.providers.base import MarketDataProvider, MarketQuote, MarketRow


class CompanyInfo(TypedDict, total=False):
    """Company information from Yahoo Finance."""
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    industry: str | None
    business_summary: str | None
    website: str | None
    country: str | None
    currency: str | None
    market_cap: int | None
    enterprise_value: int | None
    employees: int | None
    headquarters_city: str | None
    headquarters_state: str | None
    headquarters_country: str | None
    fiscal_year_end: str | None
    retrieved_at: datetime


class FinancialStatement(TypedDict, total=False):
    """Financial statement data."""
    metric: str
    value: Decimal | None
    period_end: date | None
    period_type: str  # 'annual' or 'quarterly'
    currency: str | None


class YahooFinanceProvider(MarketDataProvider):
    name = "yahoo_finance"
    max_quote_attempts = 2

    def download(self, provider_symbol: str, start_date: date, end_date: date) -> list[MarketRow]:
        frame = yf.download(
            provider_symbol,
            start=start_date.isoformat(),
            end=(end_date.fromordinal(end_date.toordinal() + 1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=True,
            progress=False,
            threads=False,
        )
        if frame is None or frame.empty:
            return []
        if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
            frame.columns = frame.columns.get_level_values(0)

        rows: list[MarketRow] = []
        for timestamp, values in frame.iterrows():
            def decimal_value(column: str) -> Decimal | None:
                value = values.get(column)
                if value is None or (hasattr(value, "item") and value.item() != value.item()):
                    return None
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError):
                    return None

            trading_date = timestamp.date() if hasattr(timestamp, "date") else timestamp
            rows.append(
                {
                    "trading_date": trading_date,
                    "open": decimal_value("Open"),
                    "high": decimal_value("High"),
                    "low": decimal_value("Low"),
                    "close": decimal_value("Close"),
                    "adjusted_close": decimal_value("Adj Close"),
                    "volume": int(values.get("Volume", 0)),
                    "dividends": decimal_value("Dividends"),
                    "stock_splits": decimal_value("Stock Splits"),
                }
            )
        return rows

    def quote(self, provider_symbol: str) -> MarketQuote:
        last_error: Exception | None = None
        for attempt in range(self.max_quote_attempts):
            try:
                ticker = yf.Ticker(provider_symbol)
                history = ticker.history(period="5d", interval="1d", auto_adjust=False)
                if history is None or history.empty:
                    raise ValueError("Yahoo Finance returned no quote data")
                if hasattr(history.columns, "nlevels") and history.columns.nlevels > 1:
                    history.columns = history.columns.get_level_values(0)
                row = history.dropna(subset=["Close"]).iloc[-1]
                previous = history.dropna(subset=["Close"]).iloc[-2] if len(history.dropna(subset=["Close"])) > 1 else None
                timestamp = history.dropna(subset=["Close"]).index[-1]
                if hasattr(timestamp, "to_pydatetime"):
                    timestamp = timestamp.to_pydatetime()
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                return {
                    "price": _decimal(row.get("Close")),
                    "previous_close": _decimal(previous.get("Close")) if previous is not None else None,
                    "open": _decimal(row.get("Open")),
                    "day_high": _decimal(row.get("High")),
                    "day_low": _decimal(row.get("Low")),
                    "volume": _integer(row.get("Volume")),
                    "currency": None,
                    "market_timestamp": timestamp.astimezone(timezone.utc),
                    "retrieved_at": datetime.now(timezone.utc),
                    "provider": self.name,
                }
            except Exception as error:
                last_error = error
                if attempt + 1 < self.max_quote_attempts:
                    continue
        raise RuntimeError(f"Yahoo Finance quote unavailable for {provider_symbol}") from last_error

    def get_company_info(self, provider_symbol: str) -> CompanyInfo:
        """Retrieve company information from Yahoo Finance."""
        try:
            ticker = yf.Ticker(provider_symbol)
            info = ticker.info or {}
            
            return CompanyInfo(
                symbol=provider_symbol,
                name=info.get("longName") or info.get("shortName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                business_summary=info.get("longBusinessSummary"),
                website=info.get("website"),
                country=info.get("country"),
                currency=info.get("currency") or info.get("financialCurrency"),
                market_cap=info.get("marketCap"),
                enterprise_value=info.get("enterpriseValue"),
                employees=info.get("fullTimeEmployees"),
                headquarters_city=info.get("city"),
                headquarters_state=info.get("state"),
                headquarters_country=info.get("country"),
                fiscal_year_end=info.get("lastFiscalYearEnd"),
                retrieved_at=datetime.now(timezone.utc),
            )
        except Exception as error:
            raise RuntimeError(f"Failed to retrieve company info for {provider_symbol}") from error

    def get_financials(
        self,
        provider_symbol: str,
        statement_type: str = "income",  # 'income', 'balance', 'cashflow'
        period_type: str = "annual",  # 'annual' or 'quarterly'
    ) -> list[FinancialStatement]:
        """
        Retrieve financial statements from Yahoo Finance.
        
        Args:
            provider_symbol: Yahoo Finance symbol
            statement_type: Type of financial statement
            period_type: 'annual' or 'quarterly'
            
        Returns:
            List of financial statement observations
        """
        try:
            ticker = yf.Ticker(provider_symbol)
            
            # Get the appropriate statement
            if statement_type == "income":
                df = ticker.quarterly_financials if period_type == "quarterly" else ticker.financials
            elif statement_type == "balance":
                df = ticker.quarterly_balance_sheet if period_type == "quarterly" else ticker.balance_sheet
            elif statement_type == "cashflow":
                df = ticker.quarterly_cashflow if period_type == "quarterly" else ticker.cashflow
            else:
                raise ValueError(f"Unknown statement type: {statement_type}")
            
            if df is None or df.empty:
                return []
            
            # Get currency
            currency = None
            try:
                info = ticker.info or {}
                currency = info.get("currency") or info.get("financialCurrency")
            except:
                pass
            
            statements: list[FinancialStatement] = []
            
            # Iterate through columns (periods)
            for period_date in df.columns:
                # Convert period to date
                if hasattr(period_date, "date"):
                    period_end = period_date.date()
                else:
                    period_end = None
                
                # Iterate through metrics (rows)
                for metric_name in df.index:
                    value = df.loc[metric_name, period_date]
                    
                    # Convert to Decimal
                    decimal_value = None
                    if value is not None and pd.notna(value):
                        try:
                            decimal_value = Decimal(str(value))
                        except (InvalidOperation, ValueError):
                            pass
                    
                    statements.append(FinancialStatement(
                        metric=str(metric_name),
                        value=decimal_value,
                        period_end=period_end,
                        period_type=period_type,
                        currency=currency,
                    ))
            
            return statements
        
        except Exception as error:
            raise RuntimeError(
                f"Failed to retrieve {period_type} {statement_type} for {provider_symbol}"
            ) from error

    def get_financial_ratios(self, provider_symbol: str) -> dict[str, Decimal | None]:
        """
        Retrieve pre-calculated financial ratios from Yahoo Finance.
        
        Returns:
            Dictionary of available financial ratios
        """
        try:
            ticker = yf.Ticker(provider_symbol)
            info = ticker.info or {}
            
            ratios: dict[str, Decimal | None] = {}
            
            # Valuation ratios
            ratios["trailing_pe"] = _decimal(info.get("trailingPE"))
            ratios["forward_pe"] = _decimal(info.get("forwardPE"))
            ratios["price_to_book"] = _decimal(info.get("priceToBook"))
            ratios["price_to_sales"] = _decimal(info.get("priceToSalesTrailing12Months"))
            ratios["ev_to_ebitda"] = _decimal(info.get("enterpriseToEbitda"))
            ratios["peg_ratio"] = _decimal(info.get("pegRatio"))
            
            # Profitability ratios
            ratios["profit_margin"] = _decimal(info.get("profitMargins"))
            ratios["operating_margin"] = _decimal(info.get("operatingMargins"))
            ratios["return_on_assets"] = _decimal(info.get("returnOnAssets"))
            ratios["return_on_equity"] = _decimal(info.get("returnOnEquity"))
            ratios["gross_margin"] = _decimal(info.get("grossMargins"))
            ratios["ebitda_margin"] = _decimal(info.get("ebitdaMargins"))
            
            # Liquidity ratios
            ratios["current_ratio"] = _decimal(info.get("currentRatio"))
            ratios["quick_ratio"] = _decimal(info.get("quickRatio"))
            
            # Leverage ratios
            ratios["debt_to_equity"] = _decimal(info.get("debtToEquity"))
            ratios["total_debt"] = _decimal(info.get("totalDebt"))
            ratios["total_cash"] = _decimal(info.get("totalCash"))
            
            # Growth metrics
            ratios["revenue_growth"] = _decimal(info.get("revenueGrowth"))
            ratios["earnings_growth"] = _decimal(info.get("earningsGrowth"))
            
            # Per-share metrics
            ratios["eps_trailing"] = _decimal(info.get("trailingEps"))
            ratios["eps_forward"] = _decimal(info.get("forwardEps"))
            ratios["book_value_per_share"] = _decimal(info.get("bookValue"))
            ratios["dividend_yield"] = _decimal(info.get("dividendYield"))
            
            return ratios
        
        except Exception as error:
            raise RuntimeError(
                f"Failed to retrieve financial ratios for {provider_symbol}"
            ) from error


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number >= 0 else None
