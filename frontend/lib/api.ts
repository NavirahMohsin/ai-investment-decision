
const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Company {
  id: number;
  name: string;
  symbol: string;
  provider_symbol: string;
  exchange: string;
  sector: string | null;
  instrument_type: string;
  is_active: boolean;
}

export interface BackendHealth {
  status: string;
  application: string;
}

export interface HistoricalPriceRecord {
  trading_date: string;
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  adjusted_close: string | number | null;
  volume: number;
  dividends: string | number | null;
  stock_splits: string | number | null;
  provider: string;
}

export interface HistoricalPriceResponse {
  symbol: string;
  provider_symbol: string;
  instrument_type: string;
  exchange: string;
  source: string;
  records: HistoricalPriceRecord[];
}

export interface IndicatorParameters {
  price_field: string;
  sma_period: number;
  ema_period: number;
  rsi_period: number;
  macd_fast_period: number;
  macd_slow_period: number;
  macd_signal_period: number;
  bollinger_period: number;
  bollinger_std_dev: number;
  atr_period: number;
}

export interface TechnicalIndicatorRecord {
  trading_date: string;
  selected_price: number | null;
  close: number | null;
  sma: number | null;
  ema: number | null;
  rsi: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  bollinger_middle: number | null;
  bollinger_upper: number | null;
  bollinger_lower: number | null;
  atr: number | null;
}

export interface TechnicalIndicatorsResponse {
  symbol: string;
  provider_symbol: string;
  exchange: string;
  instrument_type: string;
  source: string | null;
  provider: string | null;
  price_field: string;
  requested_start_date: string | null;
  requested_end_date: string | null;
  actual_first_date: string | null;
  actual_last_date: string | null;
  available_records: number;
  returned_records: number;
  parameters: IndicatorParameters;
  calculation_metadata: Record<string, string>;
  records: TechnicalIndicatorRecord[];
}

export interface FetchStockIndicatorsOptions {
  price_field?: "close" | "adjusted_close";
  sma_period?: number;
  ema_period?: number;
  rsi_period?: number;
  macd_fast_period?: number;
  macd_slow_period?: number;
  macd_signal_period?: number;
  bollinger_period?: number;
  bollinger_std_dev?: number;
  atr_period?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDateString(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function isNullableFiniteNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isFiniteInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value);
}

function isIndicatorParameters(value: unknown): value is IndicatorParameters {
  if (!isRecord(value)) {
    return false;
  }

  return (
    (value.price_field === "close" || value.price_field === "adjusted_close") &&
    isFiniteInteger(value.sma_period) &&
    isFiniteInteger(value.ema_period) &&
    isFiniteInteger(value.rsi_period) &&
    isFiniteInteger(value.macd_fast_period) &&
    isFiniteInteger(value.macd_slow_period) &&
    isFiniteInteger(value.macd_signal_period) &&
    isFiniteInteger(value.bollinger_period) &&
    typeof value.bollinger_std_dev === "number" &&
    Number.isFinite(value.bollinger_std_dev) &&
    isFiniteInteger(value.atr_period)
  );
}

function isCalculationMetadata(value: unknown): value is Record<string, string> {
  return (
    isRecord(value) &&
    Object.values(value).every((item) => typeof item === "string")
  );
}

function isTechnicalIndicatorRecord(value: unknown): value is TechnicalIndicatorRecord {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isDateString(value.trading_date) &&
    isNullableFiniteNumber(value.selected_price) &&
    isNullableFiniteNumber(value.close) &&
    isNullableFiniteNumber(value.sma) &&
    isNullableFiniteNumber(value.ema) &&
    isNullableFiniteNumber(value.rsi) &&
    isNullableFiniteNumber(value.macd) &&
    isNullableFiniteNumber(value.macd_signal) &&
    isNullableFiniteNumber(value.macd_histogram) &&
    isNullableFiniteNumber(value.bollinger_middle) &&
    isNullableFiniteNumber(value.bollinger_upper) &&
    isNullableFiniteNumber(value.bollinger_lower) &&
    isNullableFiniteNumber(value.atr)
  );
}

function isNullableDateString(value: unknown): value is string | null {
  return value === null || isDateString(value);
}

function isTechnicalIndicatorsResponse(value: unknown): value is TechnicalIndicatorsResponse {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.symbol === "string" &&
    typeof value.provider_symbol === "string" &&
    typeof value.exchange === "string" &&
    typeof value.instrument_type === "string" &&
    (typeof value.source === "string" || value.source === null) &&
    (typeof value.provider === "string" || value.provider === null) &&
    (value.price_field === "close" || value.price_field === "adjusted_close") &&
    isNullableDateString(value.requested_start_date) &&
    isNullableDateString(value.requested_end_date) &&
    isNullableDateString(value.actual_first_date) &&
    isNullableDateString(value.actual_last_date) &&
    isFiniteInteger(value.available_records) &&
    isFiniteInteger(value.returned_records) &&
    isIndicatorParameters(value.parameters) &&
    isCalculationMetadata(value.calculation_metadata) &&
    Array.isArray(value.records) &&
    value.records.every(isTechnicalIndicatorRecord)
  );
}

function isCompany(value: unknown): value is Company {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const company = value as Record<string, unknown>;
  return (
    typeof company.id === "number" &&
    typeof company.name === "string" &&
    typeof company.symbol === "string" &&
    typeof company.provider_symbol === "string" &&
    typeof company.exchange === "string" &&
    (typeof company.sector === "string" || company.sector === null) &&
    typeof company.instrument_type === "string" &&
    typeof company.is_active === "boolean"
  );
}

export async function fetchCompanies(): Promise<Company[]> {
  const response = await fetch(`${API_URL}/api/v1/companies`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Companies request failed (${response.status})`);
  }

  const payload: unknown = await response.json();
  if (!Array.isArray(payload) || !payload.every(isCompany)) {
    throw new Error("Companies response has an unexpected structure");
  }

  return payload;
}

function isHistoricalPriceRecord(value: unknown): value is HistoricalPriceRecord {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const record = value as Record<string, unknown>;
  const isNumberLike = (item: unknown) =>
    (typeof item === "number" && Number.isFinite(item)) ||
    (typeof item === "string" && item.trim() !== "" && Number.isFinite(Number(item)));

  return (
    typeof record.trading_date === "string" &&
    isNumberLike(record.open) &&
    isNumberLike(record.high) &&
    isNumberLike(record.low) &&
    isNumberLike(record.close) &&
    (record.adjusted_close === null || isNumberLike(record.adjusted_close)) &&
    typeof record.volume === "number" &&
    Number.isFinite(record.volume) &&
    (record.dividends === null || isNumberLike(record.dividends)) &&
    (record.stock_splits === null || isNumberLike(record.stock_splits)) &&
    typeof record.provider === "string"
  );
}

export async function fetchStockHistory(
  symbol: string,
  startDate: string,
  endDate: string,
): Promise<HistoricalPriceResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    interval: "1d",
  });
  const response = await fetch(
    `${API_URL}/api/v1/stocks/${encodeURIComponent(symbol)}/history?${params.toString()}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Instrument ${symbol} was not found`);
    }
    throw new Error(`Historical data request failed (${response.status})`);
  }

  const payload: unknown = await response.json();
  const responseObject =
    typeof payload === "object" && payload !== null
      ? (payload as Record<string, unknown>)
      : null;
  if (
    responseObject === null ||
    typeof responseObject.symbol !== "string" ||
    typeof responseObject.provider_symbol !== "string" ||
    typeof responseObject.instrument_type !== "string" ||
    typeof responseObject.exchange !== "string" ||
    typeof responseObject.source !== "string" ||
    !Array.isArray(responseObject.records) ||
    !responseObject.records.every(isHistoricalPriceRecord)
  ) {
    throw new Error("Historical data response has an unexpected structure");
  }

  return {
    symbol: responseObject.symbol,
    provider_symbol: responseObject.provider_symbol,
    instrument_type: responseObject.instrument_type,
    exchange: responseObject.exchange,
    source: responseObject.source,
    records: responseObject.records,
  };
}

export async function fetchStockIndicators(
  symbol: string,
  startDate: string,
  endDate: string,
  options: FetchStockIndicatorsOptions = {},
): Promise<TechnicalIndicatorsResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  });

  const response = await fetch(
    `${API_URL}/api/v1/stocks/${encodeURIComponent(symbol)}/indicators?${params.toString()}`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Instrument ${symbol} was not found`);
    }
    throw new Error(`Technical indicators request failed (${response.status})`);
  }

  const payload: unknown = await response.json();
  if (!isTechnicalIndicatorsResponse(payload)) {
    throw new Error("Technical indicators response has an unexpected structure");
  }

  return payload;
}

export async function checkBackend(): Promise<BackendHealth> {
  try {
    const response = await fetch(`${API_URL}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error("Backend request failed");
    }

    return (await response.json()) as BackendHealth;
  } catch (error) {
    console.error("Backend connection error:", error);
    throw error;
  }
}
