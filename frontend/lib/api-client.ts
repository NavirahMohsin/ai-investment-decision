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

  async generateResearchReport(ticker: string, reportType: string = 'comprehensive') {
    return this.fetch('/research/report', {
      method: 'POST',
      body: JSON.stringify({ ticker, report_type: reportType }),
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
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
