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
      direction: string,
      confidence: number,
      currentPrice: number,
      predictionPrice: number
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

  const explain = useCallback(async (ticker: string, signal: string, indicators: Record<string, any>) => {
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
    async (ticker: string, score: number, factors: Record<string, any>) => {
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
      sentimentScore: number,
      sentimentCategory: string,
      themes?: Record<string, any>
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
