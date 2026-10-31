
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

export interface MarketSnapshot {
  symbol: string;
  available: boolean;
  trading_date: string | null;
  latest_close: string | number | null;
  previous_close: string | number | null;
  absolute_change: string | number | null;
  percentage_change: string | number | null;
  provider: string | null;
}

export interface MarketOverviewResponse {
  instruments: MarketSnapshot[];
  market_status: string;
  status_timezone: string;
  retrieved_at: string | null;
}

export interface MarketQuote {
  symbol: string;
  provider_symbol: string;
  exchange: string;
  instrument_type: string;
  price: string | number | null;
  previous_close: string | number | null;
  absolute_change: string | number | null;
  percentage_change: string | number | null;
  market_timestamp: string | null;
  retrieved_at: string | null;
  freshness: string;
  provider: string;
}

export interface MarketPricesResponse {
  items: MarketQuote[];
  retrieved_at: string;
}

export interface BackendHealth {
  status: string;
  application: string;
}

export interface NewsCompanyMatch {
  company_id: number;
  symbol: string;
  name: string;
  match_method: string;
  match_confidence: string | number | null;
  matched_text: string | null;
}

export interface NewsArticle {
  id: number;
  source_id: number;
  source_provider_key: string;
  source_name: string;
  external_id: string | null;
  canonical_url: string;
  headline: string;
  summary: string | null;
  author: string | null;
  published_at: string | null;
  discovered_at: string;
  language: string | null;
  companies: NewsCompanyMatch[];
}

export interface NewsArticleDetail extends NewsArticle {
  url_hash: string;
  content_hash: string | null;
  created_at: string;
  updated_at: string;
}

export interface NewsPagination {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface NewsArticlesResponse {
  items: NewsArticle[];
  pagination: NewsPagination;
}

export interface NewsSource {
  id: number;
  name: string;
  provider_key: string;
  source_type: string;
  is_active: boolean;
  last_success_at: string | null;
  last_error: string | null;
}

export interface FetchNewsOptions {
  page?: number;
  pageSize?: number;
  company?: string;
  source?: string;
  startDate?: string;
  endDate?: string;
  search?: string;
  signal?: AbortSignal;
}

export interface NewsIngestionRun {
  id: number;
  source_id: number | null;
  source_provider_key: string | null;
  source_name: string | null;
  started_at: string;
  completed_at: string | null;
  status: string;
  articles_discovered: number;
  articles_inserted: number;
  articles_skipped: number;
  error_message: string | null;
}

export interface NewsIngestionRunsResponse {
  items: NewsIngestionRun[];
  pagination: NewsPagination;
}

export interface FetchNewsRunsOptions {
  page?: number;
  pageSize?: number;
  source?: string;
  status?: string;
  signal?: AbortSignal;
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
  vwap?: number | null;
  adx?: number | null;
  supertrend?: number | null;
  support?: number | null;
  resistance?: number | null;
  volume_ratio?: number | null;
  trend?: string;
  signal?: string;
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

function isNewsCompanyMatch(value: unknown): value is NewsCompanyMatch {
    if (!isRecord(value)) return false;
    return (
      isFiniteInteger(value.company_id) &&
      typeof value.symbol === "string" &&
      typeof value.name === "string" &&
      typeof value.match_method === "string" &&
      (value.match_confidence === null ||
        typeof value.match_confidence === "string" ||
        (typeof value.match_confidence === "number" && Number.isFinite(value.match_confidence))) &&
      (value.matched_text === null || typeof value.matched_text === "string")
    );
  }

function isNewsArticle(value: unknown): value is NewsArticle {
    if (!isRecord(value)) return false;
    return (
      isFiniteInteger(value.id) &&
      isFiniteInteger(value.source_id) &&
      typeof value.source_provider_key === "string" &&
      typeof value.source_name === "string" &&
      (value.external_id === null || typeof value.external_id === "string") &&
      typeof value.canonical_url === "string" &&
      typeof value.headline === "string" &&
      (value.summary === null || typeof value.summary === "string") &&
      (value.author === null || typeof value.author === "string") &&
      (value.published_at === null || typeof value.published_at === "string") &&
      typeof value.discovered_at === "string" &&
      (value.language === null || typeof value.language === "string") &&
      Array.isArray(value.companies) &&
      value.companies.every(isNewsCompanyMatch)
    );
  }

  function isNewsArticleDetail(value: unknown): value is NewsArticleDetail {
    return (
      isRecord(value) &&
      isNewsArticle(value) &&
      typeof value.url_hash === "string" &&
      (value.content_hash === null || typeof value.content_hash === "string") &&
      typeof value.created_at === "string" &&
      typeof value.updated_at === "string"
    );
  }

function isNewsPagination(value: unknown): value is NewsPagination {
    return (
      isRecord(value) &&
      isFiniteInteger(value.total) &&
      isFiniteInteger(value.page) &&
      isFiniteInteger(value.page_size) &&
      isFiniteInteger(value.total_pages)
    );
  }

function isNewsArticlesResponse(value: unknown): value is NewsArticlesResponse {
    return (
      isRecord(value) &&
      Array.isArray(value.items) &&
      value.items.every(isNewsArticle) &&
      isNewsPagination(value.pagination)
    );
  }

function isNewsSource(value: unknown): value is NewsSource {
    return (
      isRecord(value) &&
      isFiniteInteger(value.id) &&
      typeof value.name === "string" &&
      typeof value.provider_key === "string" &&
      typeof value.source_type === "string" &&
      typeof value.is_active === "boolean" &&
      (value.last_success_at === null || typeof value.last_success_at === "string") &&
      (value.last_error === null || typeof value.last_error === "string")
    );
  }

  function isNewsIngestionRun(value: unknown): value is NewsIngestionRun {
    if (!isRecord(value)) return false;
    return (
      isFiniteInteger(value.id) &&
      (value.source_id === null || isFiniteInteger(value.source_id)) &&
      (value.source_provider_key === null || typeof value.source_provider_key === "string") &&
      (value.source_name === null || typeof value.source_name === "string") &&
      typeof value.started_at === "string" &&
      (value.completed_at === null || typeof value.completed_at === "string") &&
      typeof value.status === "string" &&
      isFiniteInteger(value.articles_discovered) &&
      isFiniteInteger(value.articles_inserted) &&
      isFiniteInteger(value.articles_skipped) &&
      (value.error_message === null || typeof value.error_message === "string")
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

export async function fetchMarketOverview(): Promise<MarketOverviewResponse> {
  const response = await fetch(`${API_URL}/api/v1/market/overview`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Unable to load market overview (${response.status}).`);
  }

  return response.json() as Promise<MarketOverviewResponse>;
}

export async function fetchMarketQuote(symbol: string): Promise<MarketQuote> {
  const response = await fetch(`${API_URL}/api/v1/market/quotes/${encodeURIComponent(symbol)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Unable to load quote (${response.status}).`);
  }

  return response.json() as Promise<MarketQuote>;
}

export async function fetchMarketPrices(): Promise<MarketPricesResponse> {
  const response = await fetch(`${API_URL}/api/v1/market/prices`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Unable to load market prices (${response.status}).`);
  return response.json() as Promise<MarketPricesResponse>;
}

export async function fetchNews(options: FetchNewsOptions = {}): Promise<NewsArticlesResponse> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 20),
  });
  const values: Record<string, string | undefined> = {
    company: options.company,
    source: options.source,
    start_date: options.startDate,
    end_date: options.endDate,
    search: options.search,
  };
  Object.entries(values).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const response = await fetch(`${API_URL}/api/v1/news?${params.toString()}`, {
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(response.status === 404 ? "News endpoint was not found." : `News request failed (${response.status})`);
  }
  const payload: unknown = await response.json();
  if (!isNewsArticlesResponse(payload)) {
    throw new Error("News response has an unexpected structure");
  }
  return payload;
}

export async function fetchNewsSources(signal?: AbortSignal): Promise<NewsSource[]> {
  const response = await fetch(`${API_URL}/api/v1/news/sources`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(`News sources request failed (${response.status})`);
  }
  const payload: unknown = await response.json();
  if (!Array.isArray(payload) || !payload.every(isNewsSource)) {
    throw new Error("News sources response has an unexpected structure");
  }
  return payload;
}

async function fetchNewsPage(
  path: string,
  options: FetchNewsOptions,
): Promise<NewsArticlesResponse> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 20),
  });
  const values: Record<string, string | undefined> = {
    company: options.company,
    source: options.source,
    start_date: options.startDate,
    end_date: options.endDate,
    search: options.search,
  };
  Object.entries(values).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const response = await fetch(`${API_URL}${path}?${params.toString()}`, {
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) throw new Error(`News request failed (${response.status})`);
  const payload: unknown = await response.json();
  if (!isNewsArticlesResponse(payload)) {
    throw new Error("News response has an unexpected structure");
  }
  return payload;
}

export async function fetchNewsArticle(
  articleId: number,
  signal?: AbortSignal,
): Promise<NewsArticleDetail> {
  const response = await fetch(`${API_URL}/api/v1/news/${encodeURIComponent(articleId)}`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error("This news article was not found.");
    throw new Error(`News article request failed (${response.status})`);
  }
  const payload: unknown = await response.json();
  if (!isNewsArticleDetail(payload)) {
    throw new Error("News article response has an unexpected structure");
  }
  return payload;
}

export async function fetchCompanyNews(
  symbol: string,
  options: Omit<FetchNewsOptions, "company"> = {},
): Promise<NewsArticlesResponse> {
  return fetchNewsPage(`/api/v1/companies/${encodeURIComponent(symbol)}/news`, options);
}

export async function fetchNewsIngestionRuns(
  options: FetchNewsRunsOptions = {},
): Promise<NewsIngestionRunsResponse> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 20),
  });
  if (options.source) params.set("source", options.source);
  if (options.status) params.set("status", options.status);
  const response = await fetch(`${API_URL}/api/v1/news/ingestion/runs?${params.toString()}`, {
    cache: "no-store",
    signal: options.signal,
  });
  if (!response.ok) throw new Error(`Ingestion history request failed (${response.status})`);
  const payload: unknown = await response.json();
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(isNewsIngestionRun) ||
    !isNewsPagination(payload.pagination)
  ) {
    throw new Error("Ingestion history response has an unexpected structure");
  }
  return payload as unknown as NewsIngestionRunsResponse;
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
  interval: "1d" | "1wk" | "1mo" = "1d",
): Promise<HistoricalPriceResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
    interval,
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
