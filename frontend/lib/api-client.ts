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
    return this.fetch('/assistant/explain/fundamental-score', {
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
    return this.fetch('/assistant/explain/technical-signal', {
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
    return this.fetch('/explain/ml-prediction', {
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
    return this.fetch('/explain/news-sentiment', {
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
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
