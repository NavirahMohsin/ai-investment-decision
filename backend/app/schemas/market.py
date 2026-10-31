from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    symbol: str
    provider_symbol: str
    exchange: str
    sector: str | None
    instrument_type: str
    is_active: bool


class MarketSnapshot(BaseModel):
    symbol: str
    available: bool
    trading_date: date | None = None
    latest_close: Decimal | None = None
    previous_close: Decimal | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    provider: str | None = None


class MarketOverviewResponse(BaseModel):
    instruments: list[MarketSnapshot]


class HistoricalPriceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int
    dividends: Decimal | None
    stock_splits: Decimal | None
    provider: str


class HistoricalPriceResponse(BaseModel):
    symbol: str
    provider_symbol: str
    instrument_type: str
    exchange: str
    source: str
    records: list[HistoricalPriceRecord]


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    instrument_symbol: str
    requested_start_date: date
    requested_end_date: date
    records_downloaded: int
    records_inserted: int
    records_updated: int
    status: str
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class IngestionOptions(BaseModel):
    start_date: date = Field(...)
    end_date: date = Field(...)
