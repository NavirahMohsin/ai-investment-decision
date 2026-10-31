from abc import ABC, abstractmethod
from datetime import date
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


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def download(self, provider_symbol: str, start_date: date, end_date: date) -> list[MarketRow]:
        raise NotImplementedError
