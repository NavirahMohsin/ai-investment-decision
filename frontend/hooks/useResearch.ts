/**
 * Custom hooks for Research Assistant
 */

import { useState, useCallback } from 'react';
import apiClient from '@/lib/api-client';

interface UseResearchState {
  loading: boolean;
  error: string | null;
  data: any;
}

/**
 * Hook for generating company overview
 */
export function useCompanyOverview() {
  const [state, setState] = useState<UseResearchState>({
    loading: false,
    error: null,
    data: null,
  });

  const generate = useCallback(async (ticker: string, language: string = 'simple') => {
    setState({ loading: true, error: null, data: null });
    const response = await apiClient.generateCompanyOverview(ticker, language);
    
    if (response.status === 'success') {
      setState({ loading: false, error: null, data: response.data });
    } else {
      setState({ loading: false, error: response.error || 'Failed to generate overview', data: null });
    }
  }, []);

  return { ...state, generate };
}

/**
 * Hook for financial analysis
 */
export function useFinancialAnalysis() {
  const [state, setState] = useState<UseResearchState>({
    loading: false,
    error: null,
    data: null,
  });

  const analyze = useCallback(async (ticker: string, period: string = '5Y') => {
    setState({ loading: true, error: null, data: null });
    const response = await apiClient.analyzeFinancialPerformance(ticker, period);
    
    if (response.status === 'success') {
      setState({ loading: false, error: null, data: response.data });
    } else {
      setState({ loading: false, error: response.error || 'Failed to analyze', data: null });
    }
  }, []);

  return { ...state, analyze };
}

/**
 * Hook for SWOT analysis
 */
export function useSwotAnalysis() {
  const [state, setState] = useState<UseResearchState>({
    loading: false,
    error: null,
    data: null,
  });

  const generate = useCallback(async (ticker: string) => {
    setState({ loading: true, error: null, data: null });
    const response = await apiClient.generateSwotAnalysis(ticker);
    
    if (response.status === 'success') {
      setState({ loading: false, error: null, data: response.data });
    } else {
      setState({ loading: false, error: response.error || 'Failed to generate SWOT', data: null });
    }
  }, []);

  return { ...state, generate };
}

/**
 * Hook for company comparison
 */
export function useCompanyComparison() {
  const [state, setState] = useState<UseResearchState>({
    loading: false,
    error: null,
    data: null,
  });

  const compare = useCallback(async (tickers: string[]) => {
    setState({ loading: true, error: null, data: null });
    const response = await apiClient.compareCompanies(tickers);
    
    if (response.status === 'success') {
      setState({ loading: false, error: null, data: response.data });
    } else {
      setState({ loading: false, error: response.error || 'Failed to compare', data: null });
    }
  }, []);

  return { ...state, compare };
}

/**
 * Hook for research report generation
 */
export function useResearchReport() {
  const [state, setState] = useState<UseResearchState>({
    loading: false,
    error: null,
    data: null,
  });

  const generate = useCallback(async (ticker: string, reportType: string = 'comprehensive') => {
    setState({ loading: true, error: null, data: null });
    const response = await apiClient.generateResearchReport(ticker, reportType);
    
    if (response.status === 'success') {
      setState({ loading: false, error: null, data: response.data });
    } else {
      setState({ loading: false, error: response.error || 'Failed to generate report', data: null });
    }
  }, []);

  return { ...state, generate };
}

/**
 * Hook for checking research service health
 */
export function useResearchHealth() {
  const [state, setState] = useState<UseResearchState>({
    loading: false,
    error: null,
    data: null,
  });

  const check = useCallback(async () => {
    setState({ loading: true, error: null, data: null });
    const response = await apiClient.checkResearchHealth();
    
    if (response.status === 'success') {
      setState({ loading: false, error: null, data: response.data });
    } else {
      setState({ loading: false, error: response.error || 'Health check failed', data: null });
    }
  }, []);

  return { ...state, check };
}
