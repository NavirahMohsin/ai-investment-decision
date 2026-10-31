from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

import yfinance as yf

from app.services.providers.base import MarketDataProvider, MarketQuote, MarketRow


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
