
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
