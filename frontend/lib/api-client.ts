/**
 * API Client for ArthAI Backend
 * Handles all HTTP requests to the backend API
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface ApiResponse<T> {
  status: 'success' | 'error';
  data?: T;
  error?: string;
}

export interface AgentMetadata {
  name: string;
  display_name: string;
  description: string;
  scopes: string[];
  requires_db: boolean;
  requires_llm: boolean;
  is_available: boolean;
}

export interface AgentsHealthData {
  status: 'healthy' | 'degraded' | 'unhealthy';
  orchestration_available: boolean;
  registered_agents: string[];
  total_agents: number;
  gemini_available: boolean;
  groq_available: boolean;
  active_providers: string[];
  message: string;
  timestamp: string;
}

export interface AgentResultDetail {
  agent_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  summary: string;
  key_findings: string[];
  supporting_metrics: Record<string, any>;
  evidence_sources: string[];
  data_timestamps: Record<string, string>;
  confidence: string;
  missing_information: string[];
  warnings: string[];
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface AgentExecutionResponse {
  run_id: string;
  status: 'completed' | 'partial_failure' | 'failed';
  user_request: string;
  tickers: string[];
  scope: string;
  selected_agents: string[];
  execution_statuses: Record<string, string>;
  final_report?: string | null;
  agent_results: Record<string, AgentResultDetail>;
  evidence_sources: string[];
  warnings: string[];
  errors: string[];
  started_at: string;
  completed_at?: string | null;
  execution_time_seconds?: number | null;
  llm_provider_used?: string | null;
}

export interface ModelMetadata {
  model_id: string;
  model_type: string;
  version: string;
  status: string;
  created_at: string;
  updated_at: string;
  accuracy?: number | null;
  f1_score?: number | null;
  roc_auc?: number | null;
  feature_count: number;
  classes: string[];
  description?: string | null;
}

export interface PredictionResult {
  symbol: string;
  predicted_class: 'Positive' | 'Negative' | 'Neutral' | string;
  confidence: number;
  probabilities: Record<string, number>;
  horizon_days: number;
  as_of_date: string;
  model_id: string;
  prediction_id: string;
  timestamp: string;
  current_price?: number | null;
  features?: Record<string, number> | null;
}

export interface ResearchReportResult {
  report: string;
  ticker: string;
  company_name?: string | null;
  report_type: string;
  report_id?: string | null;
  structured_sections?: Record<string, string> | null;
  sources?: Array<Record<string, any>> | null;
  generated_at?: string | null;
}

export interface SavedReportSummary {
  id: number;
  report_id: string;
  ticker: string;
  company_name?: string | null;
  report_type: string;
  content_preview?: string | null;
  generated_at: string;
}

export interface SavedReportListResponse {
  reports: SavedReportSummary[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}

export interface SavedReportDetail {
  id: number;
  report_id: string;
  ticker: string;
  company_name?: string | null;
  report_type: string;
  content: string;
  structured_sections?: Record<string, string> | null;
  sources?: Array<Record<string, any>> | null;
  generated_at: string;
}

export interface PredictionHistoryItem {
  id: number;
  prediction_id: string;
  company_id: number;
  symbol: string;
  model_id?: number | null;
  horizon_days: number;
  predicted_class: string;
  confidence: number;
  probabilities?: Record<string, number> | null;
  as_of_date: string;
  current_price?: number | null;
  prediction_date: string;
  created_at: string;
}

export interface PredictionHistoryResponse {
  predictions: PredictionHistoryItem[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}

export interface BacktestRequest {
  symbol: string;
  model_id?: string;
  horizon_days?: number;
  initial_capital?: number;
  commission?: number;
  slippage?: number;
  start_date?: string;
  end_date?: string;
}

export interface BacktestTrade {
  date: string;
  direction: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  value: number;
  commission: number;
}

export interface BacktestResultData {
  backtest_id: string;
  symbol: string;
  model_id?: string | null;
  strategy_name: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_value: number;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio?: number | null;
  win_rate?: number | null;
  profit_factor?: number | null;
  num_trades: number;
  equity_curve: Array<{ date: string; value: number }>;
  trades: BacktestTrade[];
  disclaimer: string;
}

export interface IntelligenceSection {
  status: 'available' | 'unavailable';
  reason?: string | null;
  [key: string]: any;
}

export interface UnifiedStockIntelligenceResponse {
  symbol: string;
  company_name: string;
  sector?: string | null;
  industry?: string | null;
  exchange?: string | null;
  generated_at: string;
  disclaimer: string;
  warnings?: string[];
  market_intelligence: IntelligenceSection;
  technical_intelligence: IntelligenceSection;
  fundamental_intelligence: IntelligenceSection;
  news_intelligence: IntelligenceSection;
  ml_intelligence: IntelligenceSection;
  risk_intelligence: IntelligenceSection;
  agent_insights?: IntelligenceSection;
  ai_synthesis: IntelligenceSection;
}

export interface ModelEvaluationRequest {
  model_id: string;
  symbol: string;
  horizon_days?: number;
  version?: string;
  evaluation_type?: 'holdout_oos' | 'walk_forward';
  test_size?: number;
}

export interface ModelEvaluationResult {
  model_id: string;
  model_type: string;
  version: string;
  symbol?: string;
  horizon_days?: number;
  evaluation_type: string;
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
    roc_auc?: number | null;
    sample_count?: number;
  };
  confusion_matrix?: number[][];
  confusion_matrix_labels?: string[];
  class_metrics?: Record<string, any>;
  financial_metrics?: Record<string, any> | null;
  validation_window: Record<string, any>;
  disclaimer: string;
}

export interface ModelComparisonResult {
  symbol?: string;
  horizon_days?: number;
  comparable_dataset?: boolean;
  models: Array<Record<string, any>>;
  benchmark_model_id?: string | null;
  comparison_table: Array<Record<string, any>>;
  errors?: Array<{ model_id: string; error: string }>;
  disclaimer: string;
}

export interface BatchPredictionResponse {
  predictions: PredictionResult[];
  summary: {
    total_predictions: number;
    positive_count: number;
    negative_count: number;
    neutral_count: number;
    average_confidence: number;
    min_confidence: number;
    max_confidence: number;
  };
  model_id: string;
  horizon_days: number;
  timestamp: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const url = `${this.baseUrl}${endpoint}`;
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const error = await response.text();
        return {
          status: 'error',
          error: error || `HTTP ${response.status}`,
        };
      }

      const data = await response.json();
      return {
        status: 'success',
        data,
      };
    } catch (error) {
      return {
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // Research endpoints
  async generateCompanyOverview(ticker: string, language: string = 'simple') {
    return this.fetch('/research/company-overview', {
      method: 'POST',
      body: JSON.stringify({ ticker, language }),
    });
  }

  async analyzeFinancialPerformance(ticker: string, period: string = '5Y') {
    return this.fetch('/research/financial-analysis', {
      method: 'POST',
      body: JSON.stringify({ ticker, period }),
    });
  }

  async generateSwotAnalysis(ticker: string) {
    return this.fetch('/research/swot', {
      method: 'POST',
      body: JSON.stringify({ ticker }),
    });
  }

  async compareCompanies(tickers: string[]) {
    return this.fetch('/research/compare', {
      method: 'POST',
      body: JSON.stringify({ tickers }),
    });
  }

  async generateResearchReport(ticker: string, reportType: string = 'comprehensive', saveToDb: boolean = true) {
    return this.fetch<ResearchReportResult>('/research/report', {
      method: 'POST',
      body: JSON.stringify({ ticker, report_type: reportType, save_to_db: saveToDb }),
    });
  }

  async saveResearchReport(
    ticker: string,
    content: string,
    reportType: string = 'comprehensive',
    companyName?: string,
    structuredSections?: Record<string, any>,
    sources?: Array<Record<string, any>>
  ) {
    return this.fetch<ResearchReportResult>('/research/save', {
      method: 'POST',
      body: JSON.stringify({
        ticker,
        content,
        report_type: reportType,
        company_name: companyName,
        structured_sections: structuredSections,
        sources,
      }),
    });
  }

  async listSavedReports(ticker?: string, reportType?: string, limit: number = 50, offset: number = 0) {
    const params = new URLSearchParams();
    if (ticker) params.append('ticker', ticker);
    if (reportType) params.append('report_type', reportType);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    return this.fetch<SavedReportListResponse>(`/research/reports?${params.toString()}`);
  }

  async getSavedReport(reportId: string) {
    return this.fetch<SavedReportDetail>(`/research/reports/${encodeURIComponent(reportId)}`);
  }

  async deleteSavedReport(reportId: string) {
    return this.fetch<{ success: boolean; message: string; report_id: string }>(`/research/reports/${encodeURIComponent(reportId)}`, {
      method: 'DELETE',
    });
  }

  async checkResearchHealth() {
    return this.fetch('/research/health');
  }

  // Assistant endpoints
  async askQuestion(question: string, includeHistory: boolean = true) {
    return this.fetch('/assistant/ask', {
      method: 'POST',
      body: JSON.stringify({ question, include_history: includeHistory }),
    });
  }

  async explainFundamentalScore(
    ticker: string,
    score: number,
    factors: Record<string, any>
  ) {
    return this.fetch<{ explanation: string; [key: string]: any }>('/assistant/explain/fundamental-score', {
      method: 'POST',
      body: JSON.stringify({
        ticker,
        type: 'fundamental_score',
        score_or_signal: score,
        factors,
      }),
    });
  }

  async explainTechnicalSignal(
    ticker: string,
    signal: string,
    indicators: Record<string, any>
  ) {
    return this.fetch<{ explanation: string; [key: string]: any }>('/assistant/explain/technical-signal', {
      method: 'POST',
      body: JSON.stringify({
        ticker,
        type: 'technical_signal',
        score_or_signal: signal,
        factors: indicators,
      }),
    });
  }

  async compareStocks(tickers: string[]) {
    return this.fetch('/assistant/compare', {
      method: 'POST',
      body: JSON.stringify({ tickers }),
    });
  }

  async checkAssistantHealth() {
    return this.fetch('/assistant/health');
  }

  // Explanation endpoints
  async explainMlPrediction(
    ticker: string,
    direction: string,
    confidence: number,
    currentPrice: number,
    predictionPrice: number
  ) {
    return this.fetch<{ explanation: string; [key: string]: any }>('/explain/ml-prediction', {
      method: 'POST',
      body: JSON.stringify({
        ticker,
        direction,
        confidence,
        current_price: currentPrice,
        prediction_price: predictionPrice,
      }),
    });
  }

  async explainNewsSentiment(
    ticker: string,
    sentimentScore: number,
    sentimentCategory: string,
    themes?: Record<string, any>
  ) {
    return this.fetch<{ explanation: string; [key: string]: any }>('/explain/news-sentiment', {
      method: 'POST',
      body: JSON.stringify({
        ticker,
        sentiment_score: sentimentScore,
        sentiment_category: sentimentCategory,
        themes,
      }),
    });
  }

  async checkExplanationHealth() {
    return this.fetch('/explain/health');
  }

  // Multi-Agent endpoints
  async checkAgentsHealth() {
    return this.fetch<AgentsHealthData>('/agents/health');
  }

  async listAgents() {
    return this.fetch<{ agents: AgentMetadata[]; total: number }>('/agents');
  }

  async runAgentResearch(
    ticker: string,
    question?: string,
    scope: string = 'standard',
    selectedAgents?: string[]
  ) {
    return this.fetch<AgentExecutionResponse>('/agents/research', {
      method: 'POST',
      body: JSON.stringify({
        ticker,
        question: question || undefined,
        scope,
        selected_agents: selectedAgents && selectedAgents.length > 0 ? selectedAgents : undefined,
      }),
    });
  }

  async runAgentAnalyze(
    request: string,
    tickers?: string[],
    scope?: string,
    selectedAgents?: string[]
  ) {
    return this.fetch<AgentExecutionResponse>('/agents/analyze', {
      method: 'POST',
      body: JSON.stringify({
        request,
        tickers: tickers && tickers.length > 0 ? tickers : undefined,
        scope: scope || undefined,
        selected_agents: selectedAgents && selectedAgents.length > 0 ? selectedAgents : undefined,
      }),
    });
  }

  // ML Models & Prediction endpoints
  async listPredictionModels() {
    return this.fetch<{ models: ModelMetadata[]; total_count: number }>('/predictions/models');
  }

  async getPredictionModelInfo(modelId: string, version: string = 'latest') {
    return this.fetch<ModelMetadata>(`/predictions/models/${encodeURIComponent(modelId)}?version=${encodeURIComponent(version)}`);
  }

  async predictStock(
    symbol: string,
    modelId?: string,
    version: string = 'latest',
    horizonDays: number = 1,
    includeFeatures: boolean = true
  ) {
    return this.fetch<PredictionResult>('/predictions/predict', {
      method: 'POST',
      body: JSON.stringify({
        symbol,
        model_id: modelId || 'latest',
        model_version: version,
        horizon_days: horizonDays,
        include_features: includeFeatures,
      }),
    });
  }

  async predictBatch(
    symbols: string[],
    modelId?: string,
    version: string = 'latest',
    horizonDays: number = 1
  ) {
    return this.fetch<BatchPredictionResponse>('/predictions/predict/batch', {
      method: 'POST',
      body: JSON.stringify({
        symbols,
        model_id: modelId || 'latest',
        model_version: version,
        horizon_days: horizonDays,
      }),
    });
  }

  async getPredictionHistory(symbol?: string, modelId?: string, limit: number = 50, offset: number = 0) {
    const params = new URLSearchParams();
    if (symbol) params.append('symbol', symbol);
    if (modelId) params.append('model_id', modelId);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    return this.fetch<PredictionHistoryResponse>(`/predictions/history?${params.toString()}`);
  }

  async evaluateModel(request: ModelEvaluationRequest) {
    return this.fetch<ModelEvaluationResult>('/predictions/evaluate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async compareModels(
    modelIds: string[],
    symbol: string,
    horizonDays: number = 1,
    version: string = 'latest',
    testSize: number = 0.2
  ) {
    return this.fetch<ModelComparisonResult>('/predictions/compare', {
      method: 'POST',
      body: JSON.stringify({
        model_ids: modelIds,
        symbol,
        horizon_days: horizonDays,
        version,
        test_size: testSize,
      }),
    });
  }

  async runBacktest(request: BacktestRequest) {
    return this.fetch<BacktestResultData>('/predictions/backtest', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async listBacktests(symbol?: string, limit: number = 20, offset: number = 0) {
    const params = new URLSearchParams();
    if (symbol) params.append('symbol', symbol);
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    return this.fetch<{ backtests: BacktestResultData[]; total: number }>(`/predictions/backtests?${params.toString()}`);
  }

  async getBacktest(backtestId: string) {
    return this.fetch<BacktestResultData>(`/predictions/backtests/${encodeURIComponent(backtestId)}`);
  }

  async getUnifiedStockIntelligence(symbol: string) {
    return this.fetch<UnifiedStockIntelligenceResponse>(`/intelligence/${encodeURIComponent(symbol)}`);
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
