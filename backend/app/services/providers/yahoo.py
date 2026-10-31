from datetime import date
from decimal import Decimal, InvalidOperation

import yfinance as yf

from app.services.providers.base import MarketDataProvider, MarketRow


class YahooFinanceProvider(MarketDataProvider):
    name = "yahoo_finance"

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
            def decimal_value(column: str, nullable: bool = False) -> Decimal | None:
                value = values.get(column)
                if value is None or (hasattr(value, "item") and value.item() != value.item()):
                    return None if nullable else Decimal("0")
                try:
                    return Decimal(str(value))
                except (InvalidOperation, ValueError):
                    return None if nullable else Decimal("0")

            trading_date = timestamp.date() if hasattr(timestamp, "date") else timestamp
            rows.append(
                {
                    "trading_date": trading_date,
                    "open": decimal_value("Open"),
                    "high": decimal_value("High"),
                    "low": decimal_value("Low"),
                    "close": decimal_value("Close"),
                    "adjusted_close": decimal_value("Adj Close", nullable=True),
                    "volume": int(values.get("Volume", 0)),
                    "dividends": decimal_value("Dividends", nullable=True),
                    "stock_splits": decimal_value("Stock Splits", nullable=True),
                }
            )
        return rows
