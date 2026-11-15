from datetime import date, datetime, timezone
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import TypedDict, Literal
import logging
import time
import re

import yfinance as yf
import pandas as pd
from yfinance.exceptions import (
    YFPricesMissingError,
    YFRateLimitError,
    YFTickerMissingError,
    YFTzMissingError,
)

from app.services.providers.base import MarketDataProvider, MarketQuote, MarketRow

logger = logging.getLogger(__name__)


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


# Status constants (following yf_extract_new.py pattern)
DownloadStatus = Literal["ok", "empty", "rate_limited", "error", "not_found"]


class DownloadAttemptResult(TypedDict):
    """Result of attempting to download data."""
    status: DownloadStatus
    rows: list[MarketRow]
    reason: str


class _LogCapture(logging.Handler):
    """Captures yfinance's own log warnings/errors that reveal hidden failures."""
    
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.msgs: list[str] = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


class YahooFinanceProvider(MarketDataProvider):
    name = "yahoo_finance"
    max_quote_attempts = 2
    max_download_retries = 3
    base_backoff_delay = 2.0  # Start with 2 seconds for rate limits
    min_inter_request_pause = 0.6  # Minimum pause between requests
    
    def __init__(self, min_pause: float = 0.6, base_delay: float = 2.0):
        """Initialize provider with configurable delays."""
        self.min_inter_request_pause = min_pause
        self.base_backoff_delay = base_delay
        self._last_request_time: float = 0

    def _apply_pause(self) -> None:
        """Apply inter-request pause to avoid rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_inter_request_pause:
            time.sleep(self.min_inter_request_pause - elapsed)
        self._last_request_time = time.time()

    @staticmethod
    def _candidate_symbols(raw_symbol: str) -> list[str]:
        """Generate candidate symbols for Indian market symbols.
        
        For bare NSE symbols like 'INFY', tries:
        1. INFY.NS (NSE listing)
        2. INFY.BO (BSE listing)
        3. INFY (as-is, for explicit suffixes or other markets)
        """
        raw = raw_symbol.strip().upper()
        # If already has a dot or starts with ^, use as-is
        if "." in raw or raw.startswith("^"):
            return [raw]
        # For bare symbols, try NSE then BSE
        return [f"{raw}.NS", f"{raw}.BO", raw]

    def _looks_rate_limited(self, error: Exception) -> bool:
        """Detect if error is due to rate limiting."""
        message = str(error).lower()
        return any(keyword in message for keyword in [
            "too many requests",
            "429",
            "rate limit",
            "throttled",
            "yahoo has rejected",
        ])

    def _is_empty_result(self, value) -> bool:
        """Check if a result is empty (but not an error)."""
        if value is None:
            return True
        if isinstance(value, pd.DataFrame):
            return value.empty or value.dropna(how="all").empty
        if isinstance(value, pd.Series):
            return value.empty or value.dropna().empty
        if isinstance(value, dict):
            return len(value) == 0
        if isinstance(value, (list, tuple, set)):
            return len(value) == 0
        return False

    def _capture_yfinance_logs(self, fn) -> tuple[object, list[str]]:
        """Execute function while capturing yfinance warning logs."""
        cap = _LogCapture()
        lg = logging.getLogger("yfinance")
        lg.addHandler(cap)
        try:
            result = fn()
            return result, cap.msgs
        finally:
            lg.removeHandler(cap)

    def resolve_symbol(self, raw_symbol: str) -> tuple[str | None, DownloadStatus, list[str]]:
        """Resolve a symbol to a working Yahoo Finance ticker.
        
        Returns:
            (resolved_symbol, status, tried_list)
            - resolved_symbol: Working ticker or None
            - status: 'ok', 'not_found', or 'rate_limited'
            - tried_list: List of attempted symbols with results
        """
        tried: list[str] = []
        saw_rate_limit = False
        
        for candidate in self._candidate_symbols(raw_symbol):
            try:
                self._apply_pause()
                # Test with 1-day history to validate symbol
                ticker = yf.Ticker(candidate)
                history, _ = self._capture_yfinance_logs(
                    lambda: ticker.history(period="1d", interval="1d", auto_adjust=False)
                )
                if not self._is_empty_result(history):
                    tried.append(f"{candidate}:ok")
                    return candidate, "ok", tried
                tried.append(f"{candidate}:empty")
            except (YFTickerMissingError, YFPricesMissingError):
                tried.append(f"{candidate}:not_found")
            except Exception as e:
                if self._looks_rate_limited(e):
                    tried.append(f"{candidate}:rate_limited")
                    saw_rate_limit = True
                else:
                    tried.append(f"{candidate}:{type(e).__name__}")
        
        # Return appropriate failure status
        status: DownloadStatus = "rate_limited" if saw_rate_limit else "not_found"
        return None, status, tried

    def download(self, provider_symbol: str, start_date: date, end_date: date) -> list[MarketRow]:
        """Download market data with retry logic and rate limit handling."""
        result = self._download_with_retry(provider_symbol, start_date, end_date)
        if result["status"] == "ok":
            return result["rows"]
        elif result["status"] == "empty":
            logger.warning(
                f"No data for {provider_symbol}: {result['reason']}"
            )
            return []
        else:
            # For rate_limited or error, raise to be handled by caller
            raise RuntimeError(
                f"Failed to download {provider_symbol}: "
                f"{result['status']} - {result['reason']}"
            )

    def _download_with_retry(
        self, provider_symbol: str, start_date: date, end_date: date
    ) -> DownloadAttemptResult:
        """Download with exponential backoff on rate limits."""
        delay = self.base_backoff_delay
        last_error: Exception | None = None
        
        for attempt in range(1, self.max_download_retries + 1):
            try:
                self._apply_pause()
                frame, logs = self._capture_yfinance_logs(
                    lambda: yf.download(
                        provider_symbol,
                        start=start_date.isoformat(),
                        end=(end_date.fromordinal(end_date.toordinal() + 1)).isoformat(),
                        interval="1d",
                        auto_adjust=False,
                        actions=True,
                        progress=False,
                        threads=False,
                    )
                )
                
                if frame is None or frame.empty:
                    # Check if logs reveal actual error
                    if logs:
                        reason = self._clean_log_message(logs[-1])
                        return DownloadAttemptResult(
                            status="empty",
                            rows=[],
                            reason=f"Yahoo returned no data - {reason}"
                        )
                    return DownloadAttemptResult(
                        status="empty",
                        rows=[],
                        reason="Yahoo returned no data (can be legitimate)"
                    )
                
                # Handle multi-index columns (multiple symbols)
                if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
                    frame.columns = frame.columns.get_level_values(0)
                
                rows = self._frame_to_rows(frame)
                return DownloadAttemptResult(
                    status="ok",
                    rows=rows,
                    reason=""
                )
                
            except (YFTickerMissingError, YFPricesMissingError) as e:
                return DownloadAttemptResult(
                    status="empty",
                    rows=[],
                    reason=f"{type(e).__name__}: {e}"
                )
            except Exception as e:
                last_error = e
                if self._looks_rate_limited(e):
                    if attempt < self.max_download_retries:
                        logger.warning(
                            f"Rate limited on attempt {attempt}/{self.max_download_retries}, "
                            f"backing off {delay}s"
                        )
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                        continue
                    return DownloadAttemptResult(
                        status="rate_limited",
                        rows=[],
                        reason=f"{type(e).__name__}: {e} (after {attempt} attempts)"
                    )
                else:
                    # Non-rate-limit error
                    if attempt < self.max_download_retries:
                        logger.warning(f"Download failed on attempt {attempt}, retrying: {e}")
                        time.sleep(2.0)
                        continue
                    return DownloadAttemptResult(
                        status="error",
                        rows=[],
                        reason=f"{type(e).__name__}: {e}"
                    )
        
        return DownloadAttemptResult(
            status="error",
            rows=[],
            reason="Exhausted all retry attempts"
        )

    def _frame_to_rows(self, frame: pd.DataFrame) -> list[MarketRow]:
        """Convert DataFrame to MarketRow list."""
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

    @staticmethod
    def _clean_log_message(msg: str) -> str:
        """Extract meaningful error message from yfinance log."""
        import re
        # Try to extract description from JSON-like error
        match = re.search(r'"description"\s*:\s*"([^"]+)"', msg)
        if match:
            code_match = re.search(r"HTTP Error (\d+)", msg)
            http_prefix = f"HTTP {code_match.group(1)}: " if code_match else ""
            return f"Yahoo {http_prefix}{match.group(1)}"
        # Fallback: clean up whitespace
        return re.sub(r"\s+", " ", msg).strip()[:160]

    def quote(self, provider_symbol: str) -> MarketQuote:
        """Get current quote with retry logic."""
        last_error: Exception | None = None
        for attempt in range(self.max_quote_attempts):
            try:
                self._apply_pause()
                ticker = yf.Ticker(provider_symbol)
                history, _ = self._capture_yfinance_logs(
                    lambda: ticker.history(period="5d", interval="1d", auto_adjust=False)
                )
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
                    if self._looks_rate_limited(error):
                        time.sleep(2.0)
                    continue
        raise RuntimeError(f"Yahoo Finance quote unavailable for {provider_symbol}") from last_error

    def get_company_info(self, provider_symbol: str) -> CompanyInfo:
        """Retrieve company information from Yahoo Finance."""
        try:
            self._apply_pause()
            ticker = yf.Ticker(provider_symbol)
            info, _ = self._capture_yfinance_logs(lambda: ticker.info or {})
            
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
            self._apply_pause()
            ticker = yf.Ticker(provider_symbol)
            
            # Get the appropriate statement
            if statement_type == "income":
                df, _ = self._capture_yfinance_logs(
                    lambda: ticker.quarterly_financials if period_type == "quarterly" else ticker.financials
                )
            elif statement_type == "balance":
                df, _ = self._capture_yfinance_logs(
                    lambda: ticker.quarterly_balance_sheet if period_type == "quarterly" else ticker.balance_sheet
                )
            elif statement_type == "cashflow":
                df, _ = self._capture_yfinance_logs(
                    lambda: ticker.quarterly_cashflow if period_type == "quarterly" else ticker.cashflow
                )
            else:
                raise ValueError(f"Unknown statement type: {statement_type}")
            
            if df is None or df.empty:
                return []
            
            # Get currency
            currency = None
            try:
                info, _ = self._capture_yfinance_logs(lambda: ticker.info or {})
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
            self._apply_pause()
            ticker = yf.Ticker(provider_symbol)
            info, _ = self._capture_yfinance_logs(lambda: ticker.info or {})
            
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
