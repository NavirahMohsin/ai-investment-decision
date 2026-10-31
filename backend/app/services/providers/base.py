from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import TypedDict


class MarketRow(TypedDict):
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int
    dividends: Decimal | None
    stock_splits: Decimal | None


class MarketQuote(TypedDict):
    price: Decimal | None
    previous_close: Decimal | None
    open: Decimal | None
    day_high: Decimal | None
    day_low: Decimal | None
    volume: int | None
    currency: str | None
    market_timestamp: datetime | None
    retrieved_at: datetime
    provider: str


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def download(self, provider_symbol: str, start_date: date, end_date: date) -> list[MarketRow]:
        raise NotImplementedError

    def quote(self, provider_symbol: str) -> MarketQuote:
        raise NotImplementedError
