/**
 * Custom hooks for AI Explanations
 */

import { useState, useCallback } from 'react';
import apiClient from '@/lib/api-client';

interface UseExplanationState {
  loading: boolean;
  error: string | null;
  explanation: string | null;
}

/**
 * Hook for explaining ML predictions
 */
export function useMlPredictionExplanation() {
  const [state, setState] = useState<UseExplanationState>({
    loading: false,
    error: null,
    explanation: null,
  });

  const explain = useCallback(
    async (
      ticker: string,
      direction: string = 'Positive',
      confidence: number = 0.75,
      currentPrice: number = 100,
      predictionPrice: number = 105
    ) => {
      setState({ loading: true, error: null, explanation: null });
      const response = await apiClient.explainMlPrediction(
        ticker,
        direction,
        confidence,
        currentPrice,
        predictionPrice
      );

      if (response.status === 'success') {
        setState({
          loading: false,
          error: null,
          explanation: response.data?.explanation || null,
        });
      } else {
        setState({
          loading: false,
          error: response.error || 'Failed to generate explanation',
          explanation: null,
        });
      }
    },
    []
  );

  return { ...state, explain };
}

/**
 * Hook for explaining technical signals
 */
export function useTechnicalSignalExplanation() {
  const [state, setState] = useState<UseExplanationState>({
    loading: false,
    error: null,
    explanation: null,
  });

  const explain = useCallback(async (ticker: string, signal: string = 'Bullish', indicators: Record<string, any> = { rsi: 55 }) => {
    setState({ loading: true, error: null, explanation: null });
    const response = await apiClient.explainTechnicalSignal(ticker, signal, indicators);

    if (response.status === 'success') {
      setState({
        loading: false,
        error: null,
        explanation: response.data?.explanation || null,
      });
    } else {
      setState({
        loading: false,
        error: response.error || 'Failed to generate explanation',
        explanation: null,
      });
    }
  }, []);

  return { ...state, explain };
}

/**
 * Hook for explaining fundamental scores
 */
export function useFundamentalScoreExplanation() {
  const [state, setState] = useState<UseExplanationState>({
    loading: false,
    error: null,
    explanation: null,
  });

  const explain = useCallback(
    async (ticker: string, score: number = 75, factors: Record<string, any> = { profitability: 'high' }) => {
      setState({ loading: true, error: null, explanation: null });
      const response = await apiClient.explainFundamentalScore(ticker, score, factors);

      if (response.status === 'success') {
        setState({
          loading: false,
          error: null,
          explanation: response.data?.explanation || null,
        });
      } else {
        setState({
          loading: false,
          error: response.error || 'Failed to generate explanation',
          explanation: null,
        });
      }
    },
    []
  );

  return { ...state, explain };
}

/**
 * Hook for explaining news sentiment
 */
export function useNewsSentimentExplanation() {
  const [state, setState] = useState<UseExplanationState>({
    loading: false,
    error: null,
    explanation: null,
  });

  const explain = useCallback(
    async (
      ticker: string,
      sentimentScore: number = 0.6,
      sentimentCategory: string = 'Positive',
      themes: Record<string, any> = {}
    ) => {
      setState({ loading: true, error: null, explanation: null });
      const response = await apiClient.explainNewsSentiment(
        ticker,
        sentimentScore,
        sentimentCategory,
        themes
      );

      if (response.status === 'success') {
        setState({
          loading: false,
          error: null,
          explanation: response.data?.explanation || null,
        });
      } else {
        setState({
          loading: false,
          error: response.error || 'Failed to generate explanation',
          explanation: null,
        });
      }
    },
    []
  );

  return { ...state, explain };
}
