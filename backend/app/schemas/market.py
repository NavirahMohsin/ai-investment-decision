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


class IndicatorParametersResponse(BaseModel):
    price_field: str
    sma_period: int
    ema_period: int
    rsi_period: int
    macd_fast_period: int
    macd_slow_period: int
    macd_signal_period: int
    bollinger_period: int
    bollinger_std_dev: float
    atr_period: int


class TechnicalIndicatorRecord(BaseModel):
    trading_date: date
    selected_price: float | None
    close: float | None
    sma: float | None
    ema: float | None
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bollinger_middle: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    atr: float | None


class TechnicalIndicatorsResponse(BaseModel):
    symbol: str
    provider_symbol: str
    exchange: str
    instrument_type: str
    source: str | None
    provider: str | None
    price_field: str
    requested_start_date: date | None
    requested_end_date: date | None
    actual_first_date: date | None
    actual_last_date: date | None
    available_records: int
    returned_records: int
    parameters: IndicatorParametersResponse
    calculation_metadata: dict[str, str]
    records: list[TechnicalIndicatorRecord]


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
