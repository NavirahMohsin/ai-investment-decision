'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Cpu,
  TrendingUp,
  Award,
  Calendar,
  RefreshCw,
  AlertTriangle,
  Play,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Sparkles,
  Info,
  FlaskConical,
  GitCompare,
  LineChart,
  History,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { fetchCompanies, Company } from '@/lib/api';
import apiClient, {
  ModelMetadata,
  PredictionResult,
  PredictionHistoryItem,
  ModelEvaluationResult,
  ModelComparisonResult,
  BacktestResultData,
} from '@/lib/api-client';

const MODEL_TYPE_BADGES: Record<string, { label: string; color: string }> = {
  xgboost: { label: 'XGBoost', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  lightgbm: { label: 'LightGBM', color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' },
  random_forest: { label: 'Random Forest', color: 'bg-purple-500/10 text-purple-400 border-purple-500/30' },
  logistic_regression: { label: 'Logistic Regression', color: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
};

function normalizeClass(label?: string | null) {
  if (!label) return 'Neutral';
  const lower = label.toLowerCase();
  if (lower === 'positive') return 'Positive';
  if (lower === 'negative') return 'Negative';
  if (lower === 'neutral') return 'Neutral';
  return label;
}

export default function ModelsEvaluationPage() {
  const [models, setModels] = useState<ModelMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<ModelMetadata | null>(null);
  const [compareSelection, setCompareSelection] = useState<string[]>([]);

  const [companies, setCompanies] = useState<Company[]>([]);
  const [testSymbol, setTestSymbol] = useState('RELIANCE');
  const [evalSymbol, setEvalSymbol] = useState('RELIANCE');
  const [testHorizon, setTestHorizon] = useState<number>(1);
  const [evalHorizon, setEvalHorizon] = useState<number>(1);
  const [evalType, setEvalType] = useState<'holdout_oos' | 'walk_forward'>('holdout_oos');

  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionResult, setPredictionResult] = useState<PredictionResult | null>(null);
  const [predictionError, setPredictionError] = useState<string | null>(null);

  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluation, setEvaluation] = useState<ModelEvaluationResult | null>(null);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);

  const [isComparing, setIsComparing] = useState(false);
  const [comparison, setComparison] = useState<ModelComparisonResult | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtest, setBacktest] = useState<BacktestResultData | null>(null);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestHistory, setBacktestHistory] = useState<BacktestResultData[]>([]);

  const [predictionHistory, setPredictionHistory] = useState<PredictionHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const loadModels = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.listPredictionModels();
      if (res.status === 'success' && res.data) {
        setModels(res.data.models || []);
        if (res.data.models && res.data.models.length > 0) {
          const best = [...res.data.models].sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0))[0];
          setSelectedModel(best);
        }
      } else {
        setErrorMsg(res.error || 'Failed to retrieve model registry.');
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Error connecting to model server.');
    } finally {
      setLoading(false);
    }
  };

  const loadPredictionHistory = async (symbol?: string, modelId?: string) => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await apiClient.getPredictionHistory(symbol, modelId, 25, 0);
      if (res.status === 'success' && res.data) {
        setPredictionHistory(res.data.predictions || []);
      } else {
        setHistoryError(res.error || 'Failed to load prediction history.');
      }
    } catch (err: any) {
      setHistoryError(err?.message || 'Prediction history request failed.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadBacktestHistory = async (symbol?: string) => {
    try {
      const res = await apiClient.listBacktests(symbol, 10, 0);
      if (res.status === 'success' && res.data) {
        setBacktestHistory(res.data.backtests || []);
      }
    } catch {
      // non-blocking
    }
  };

  useEffect(() => {
    loadModels();
    fetchCompanies()
      .then(setCompanies)
      .catch((e) => console.warn('Could not load companies for test:', e));
    loadPredictionHistory();
    loadBacktestHistory();
  }, []);

  const filteredModels = useMemo(() => {
    return models.filter((m) => {
      const matchesType = typeFilter === 'all' || m.model_type.toLowerCase() === typeFilter.toLowerCase();
      const matchesSearch =
        !searchQuery.trim() ||
        m.model_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.model_type.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesType && matchesSearch;
    });
  }, [models, typeFilter, searchQuery]);

  const bestAccuracy = useMemo(() => {
    if (models.length === 0) return 0;
    return Math.max(...models.map((m) => m.accuracy || 0));
  }, [models]);

  const bestF1 = useMemo(() => {
    if (models.length === 0) return 0;
    return Math.max(...models.map((m) => m.f1_score || 0));
  }, [models]);

  const toggleCompare = (modelId: string) => {
    setCompareSelection((prev) => {
      if (prev.includes(modelId)) return prev.filter((id) => id !== modelId);
      if (prev.length >= 4) return prev;
      return [...prev, modelId];
    });
  };

  const handleRunTestPrediction = async () => {
    const sym = testSymbol.trim().toUpperCase();
    if (!sym) return;

    setIsPredicting(true);
    setPredictionError(null);
    setPredictionResult(null);

    try {
      const res = await apiClient.predictStock(
        sym,
        selectedModel?.model_id || 'latest',
        selectedModel?.version || 'latest',
        testHorizon,
        true
      );

      if (res.status === 'success' && res.data) {
        setPredictionResult(res.data);
        await loadPredictionHistory(sym, selectedModel?.model_id);
      } else {
        setPredictionError(res.error || 'Prediction generation failed.');
      }
    } catch (err: any) {
      setPredictionError(err?.message || 'Error invoking model prediction.');
    } finally {
      setIsPredicting(false);
    }
  };

  const handleEvaluate = async () => {
    if (!selectedModel) {
      setEvaluationError('Select a model first.');
      return;
    }
    const sym = evalSymbol.trim().toUpperCase();
    if (!sym) return;

    setIsEvaluating(true);
    setEvaluationError(null);
    setEvaluation(null);
    try {
      const res = await apiClient.evaluateModel({
        model_id: selectedModel.model_id,
        symbol: sym,
        horizon_days: evalHorizon,
        version: selectedModel.version || 'latest',
        evaluation_type: evalType,
      });
      if (res.status === 'success' && res.data) {
        setEvaluation(res.data);
      } else {
        setEvaluationError(res.error || 'Evaluation failed.');
      }
    } catch (err: any) {
      setEvaluationError(err?.message || 'Evaluation request failed.');
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleCompare = async () => {
    if (compareSelection.length < 2) {
      setComparisonError('Select at least two models to compare.');
      return;
    }
    const sym = evalSymbol.trim().toUpperCase();
    if (!sym) return;

    setIsComparing(true);
    setComparisonError(null);
    setComparison(null);
    try {
      const res = await apiClient.compareModels(compareSelection, sym, evalHorizon);
      if (res.status === 'success' && res.data) {
        setComparison(res.data);
      } else {
        setComparisonError(res.error || 'Comparison failed.');
      }
    } catch (err: any) {
      setComparisonError(err?.message || 'Comparison request failed.');
    } finally {
      setIsComparing(false);
    }
  };

  const handleBacktest = async () => {
    const sym = evalSymbol.trim().toUpperCase();
    if (!sym) return;

    setIsBacktesting(true);
    setBacktestError(null);
    setBacktest(null);
    try {
      const res = await apiClient.runBacktest({
        symbol: sym,
        model_id: selectedModel?.model_id || 'latest',
        horizon_days: evalHorizon,
        initial_capital: 100000,
      });
      if (res.status === 'success' && res.data) {
        setBacktest(res.data);
        await loadBacktestHistory(sym);
      } else {
        setBacktestError(res.error || 'Backtest failed.');
      }
    } catch (err: any) {
      setBacktestError(err?.message || 'Backtest request failed.');
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      <div className="border-b border-border/60 bg-card/40 backdrop-blur px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 font-semibold text-primary">
              <Cpu className="size-4" />
              ArthAI ML Model Registry & Evaluation
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-muted-foreground">Out-of-sample metrics · Walk-forward · Backtests</span>
          </div>
          <div className="flex items-center gap-4 text-muted-foreground">
            <span>
              Registered Models: <strong className="text-foreground">{models.length}</strong>
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span>
              Best Accuracy:{' '}
              <strong className="text-emerald-400 font-mono">{(bestAccuracy * 100).toFixed(1)}%</strong>
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2.5">
              Model Evaluation & Benchmarking
              <Badge variant="outline" className="text-purple-400 border-purple-500/30 font-mono text-[10px]">
                PHASE 6
              </Badge>
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Inspect registered models, run genuine out-of-sample evaluation, compare algorithms, execute
              backtests, and review persisted prediction history.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={loadModels} disabled={loading} className="gap-1.5 text-xs">
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Models
          </Button>
        </div>

        {errorMsg && (
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-4 flex items-start gap-3 text-rose-300 text-sm">
            <AlertTriangle className="size-5 shrink-0 text-rose-400 mt-0.5" />
            <div className="flex-1">
              <strong className="font-semibold block mb-0.5">Model Server Notice</strong>
              {errorMsg}
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-xs underline">
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="border-border/80 bg-card/60 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Available Models</span>
              <Cpu className="size-4 text-primary" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono">{models.length}</div>
          </Card>
          <Card className="border-border/80 bg-card/60 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Top Accuracy</span>
              <Award className="size-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-emerald-400">
              {(bestAccuracy * 100).toFixed(1)}%
            </div>
          </Card>
          <Card className="border-border/80 bg-card/60 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Top F1</span>
              <TrendingUp className="size-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-cyan-400">{(bestF1 * 100).toFixed(1)}%</div>
          </Card>
          <Card className="border-border/80 bg-card/60 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Horizons</span>
              <Calendar className="size-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-purple-400">1D, 5D, 20D</div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-7 space-y-6">
            <Card className="border-border/80 bg-card/60 shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Layers className="size-4 text-primary" />
                      Model Catalog
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Select a model for inference/evaluation. Check up to 4 models for comparison.
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    {(['all', 'xgboost', 'lightgbm', 'random_forest', 'logistic_regression'] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTypeFilter(t)}
                        className={`px-2 py-1 rounded text-[11px] capitalize border transition-all ${
                          typeFilter === t
                            ? 'bg-primary text-primary-foreground font-medium border-primary'
                            : 'bg-muted/40 text-muted-foreground hover:text-foreground border-border/60'
                        }`}
                      >
                        {t.replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="pt-2">
                  <Input
                    type="text"
                    placeholder="Search by model ID or version..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="text-xs h-8"
                  />
                </div>
              </CardHeader>
              <CardContent className="space-y-2.5 pt-0">
                {loading ? (
                  <div className="py-12 text-center text-xs text-muted-foreground space-y-2">
                    <RefreshCw className="size-5 animate-spin mx-auto text-primary" />
                    <p>Loading model registry...</p>
                  </div>
                ) : filteredModels.length === 0 ? (
                  <div className="py-12 text-center text-xs text-muted-foreground space-y-2">
                    <Cpu className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-foreground font-medium">No models match criteria</p>
                  </div>
                ) : (
                  filteredModels.map((m) => {
                    const isSelected = selectedModel?.model_id === m.model_id;
                    const inCompare = compareSelection.includes(m.model_id);
                    const badgeInfo = MODEL_TYPE_BADGES[m.model_type.toLowerCase()] || {
                      label: m.model_type,
                      color: 'bg-muted text-muted-foreground',
                    };
                    return (
                      <div
                        key={`${m.model_id}_${m.version}`}
                        className={`p-3 rounded-lg border transition-all text-xs ${
                          isSelected
                            ? 'bg-primary/5 border-primary shadow-xs ring-1 ring-primary/30'
                            : 'bg-card border-border hover:bg-muted/30'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                          <button
                            type="button"
                            onClick={() => setSelectedModel(m)}
                            className="flex items-center gap-2 text-left"
                          >
                            <span className="font-mono font-semibold text-foreground text-xs">{m.model_id}</span>
                            <Badge variant="outline" className={`text-[10px] scale-90 ${badgeInfo.color}`}>
                              {badgeInfo.label}
                            </Badge>
                          </button>
                          <div className="flex items-center gap-3 font-mono text-[11px]">
                            {m.accuracy != null && (
                              <span className="text-emerald-400">
                                Acc: <strong>{(m.accuracy * 100).toFixed(1)}%</strong>
                              </span>
                            )}
                            {m.f1_score != null && (
                              <span className="text-cyan-400">
                                F1: <strong>{(m.f1_score * 100).toFixed(1)}%</strong>
                              </span>
                            )}
                            <label className="flex items-center gap-1 text-muted-foreground cursor-pointer">
                              <input
                                type="checkbox"
                                checked={inCompare}
                                onChange={() => toggleCompare(m.model_id)}
                                aria-label={`Compare ${m.model_id}`}
                              />
                              Compare
                            </label>
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                          <span>
                            Version: <strong className="text-foreground">{m.version}</strong>
                          </span>
                          <span>
                            Features: <strong className="text-foreground">{m.feature_count}</strong>
                          </span>
                          <span>
                            Classes: <strong className="text-foreground">{m.classes.join(', ')}</strong>
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>

            {/* Evaluation / Compare / Backtest */}
            <Card className="border-border/80 bg-card/60 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FlaskConical className="size-4 text-primary" />
                  Out-of-Sample Evaluation & Backtesting
                </CardTitle>
                <CardDescription className="text-xs">
                  Metrics are computed on chronologically held-out data with horizon embargo. No fabricated scores.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <label className="font-medium">Evaluation Symbol</label>
                    <Input
                      value={evalSymbol}
                      onChange={(e) => setEvalSymbol(e.target.value.toUpperCase())}
                      className="font-mono uppercase text-xs h-8"
                    />
                    <div className="flex flex-wrap gap-1">
                      {(companies.slice(0, 4).map((c) => c.symbol).concat(['RELIANCE', 'INFY', 'TCS'])
                        .filter((v, i, a) => a.indexOf(v) === i)
                        .slice(0, 4)).map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setEvalSymbol(s)}
                          className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                            evalSymbol === s
                              ? 'bg-primary/20 text-primary border-primary/40'
                              : 'bg-muted/40 text-muted-foreground border-border/40'
                          }`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="font-medium">Horizon</label>
                    <div className="grid grid-cols-3 gap-1">
                      {[1, 5, 20].map((h) => (
                        <button
                          key={h}
                          type="button"
                          onClick={() => setEvalHorizon(h)}
                          className={`py-1.5 rounded border ${
                            evalHorizon === h
                              ? 'bg-primary/15 border-primary text-primary font-semibold'
                              : 'bg-muted/30 border-border/60 text-muted-foreground'
                          }`}
                        >
                          {h}D
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="font-medium">Evaluation Mode</label>
                    <div className="grid grid-cols-2 gap-1">
                      {(
                        [
                          { id: 'holdout_oos', label: 'Holdout OOS' },
                          { id: 'walk_forward', label: 'Walk-Forward' },
                        ] as const
                      ).map((mode) => (
                        <button
                          key={mode.id}
                          type="button"
                          onClick={() => setEvalType(mode.id)}
                          className={`py-1.5 rounded border text-[11px] ${
                            evalType === mode.id
                              ? 'bg-primary/15 border-primary text-primary font-semibold'
                              : 'bg-muted/30 border-border/60 text-muted-foreground'
                          }`}
                        >
                          {mode.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button onClick={handleEvaluate} disabled={isEvaluating || !selectedModel} className="gap-1.5">
                    {isEvaluating ? <RefreshCw className="size-3.5 animate-spin" /> : <FlaskConical className="size-3.5" />}
                    Evaluate Selected
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleCompare}
                    disabled={isComparing || compareSelection.length < 2}
                    className="gap-1.5"
                  >
                    {isComparing ? <RefreshCw className="size-3.5 animate-spin" /> : <GitCompare className="size-3.5" />}
                    Compare ({compareSelection.length})
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleBacktest}
                    disabled={isBacktesting}
                    className="gap-1.5"
                  >
                    {isBacktesting ? <RefreshCw className="size-3.5 animate-spin" /> : <LineChart className="size-3.5" />}
                    Run Backtest
                  </Button>
                </div>

                {evaluationError && (
                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">
                    {evaluationError}
                  </div>
                )}
                {comparisonError && (
                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">
                    {comparisonError}
                  </div>
                )}
                {backtestError && (
                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">
                    {backtestError}
                  </div>
                )}

                {evaluation && (
                  <div className="rounded-lg border border-border bg-card p-3 space-y-3">
                    <div className="flex flex-wrap justify-between gap-2">
                      <strong className="font-mono">{evaluation.model_id}</strong>
                      <Badge variant="outline" className="text-[10px]">
                        {evaluation.evaluation_type}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="rounded bg-muted/30 p-2">
                        Acc <strong className="block font-mono">{(evaluation.metrics.accuracy * 100).toFixed(2)}%</strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Precision <strong className="block font-mono">{(evaluation.metrics.precision * 100).toFixed(2)}%</strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Recall <strong className="block font-mono">{(evaluation.metrics.recall * 100).toFixed(2)}%</strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        F1 <strong className="block font-mono">{(evaluation.metrics.f1 * 100).toFixed(2)}%</strong>
                      </div>
                    </div>
                    {evaluation.confusion_matrix && (
                      <div>
                        <p className="text-[11px] text-muted-foreground mb-1">
                          Confusion matrix ({(evaluation.confusion_matrix_labels || []).join(' / ')})
                        </p>
                        <div className="overflow-x-auto">
                          <table className="text-[11px] font-mono">
                            <tbody>
                              {evaluation.confusion_matrix.map((row, i) => (
                                <tr key={i}>
                                  {row.map((cell, j) => (
                                    <td key={j} className="border border-border/60 px-2 py-1 text-center">
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    {evaluation.financial_metrics && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                        <div>
                          Return:{' '}
                          <strong className={`font-mono ${(evaluation.financial_metrics.total_return ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {(evaluation.financial_metrics.total_return ?? 0) >= 0 ? '+' : ''}
                            {typeof evaluation.financial_metrics.total_return === 'number'
                              ? evaluation.financial_metrics.total_return.toFixed(2)
                              : evaluation.financial_metrics.total_return ?? '—'}%
                          </strong>
                        </div>
                        <div>
                          Max DD:{' '}
                          <strong className="font-mono text-rose-400">
                            {typeof evaluation.financial_metrics.max_drawdown === 'number'
                              ? `-${Math.abs(evaluation.financial_metrics.max_drawdown).toFixed(2)}%`
                              : `${evaluation.financial_metrics.max_drawdown ?? '—'}%`}
                          </strong>
                        </div>
                        <div>
                          Sharpe:{' '}
                          <strong className="font-mono">
                            {typeof evaluation.financial_metrics.sharpe_ratio === 'number'
                              ? evaluation.financial_metrics.sharpe_ratio.toFixed(2)
                              : evaluation.financial_metrics.sharpe_ratio ?? '—'}
                          </strong>
                        </div>
                        <div>Trades: <strong className="font-mono">{evaluation.financial_metrics.num_trades ?? '—'}</strong></div>
                      </div>
                    )}
                    {evaluation.data_leakage_risk && (
                      <div className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-[11px] text-amber-300 flex items-center gap-2">
                        <AlertTriangle className="size-3.5 shrink-0" />
                        <span>Data integrity note: {evaluation.data_leakage_risk}</span>
                      </div>
                    )}
                    {evaluation.evaluation_method && (
                      <div className="text-[10px] text-muted-foreground">
                        Method: <span className="font-mono">{evaluation.evaluation_method}</span>
                        {evaluation.retraining_per_fold === false && ' (frozen model)'}
                      </div>
                    )}
                    <p className="text-[10px] text-muted-foreground">{evaluation.disclaimer}</p>
                  </div>
                )}

                {comparison && (
                  <div className="rounded-lg border border-border bg-card p-3 space-y-2 overflow-x-auto">
                    <div className="flex justify-between gap-2">
                      <strong>Model Comparison</strong>
                      <span className="text-[10px] text-muted-foreground">
                        Benchmark: {comparison.benchmark_model_id || '—'}
                      </span>
                    </div>
                    <table className="w-full min-w-[640px] text-[11px]">
                      <thead>
                        <tr className="text-muted-foreground border-b border-border/60">
                          <th className="text-left py-1.5">Model</th>
                          <th className="text-right">Acc</th>
                          <th className="text-right">Prec</th>
                          <th className="text-right">Recall</th>
                          <th className="text-right">F1</th>
                          <th className="text-right">Return%</th>
                          <th className="text-right">MaxDD%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.comparison_table.map((row) => (
                          <tr key={row.model_id} className="border-b border-border/40">
                            <td className="py-1.5 font-mono">{row.model_id}</td>
                            <td className="text-right font-mono">{((row.accuracy || 0) * 100).toFixed(1)}%</td>
                            <td className="text-right font-mono">{((row.precision || 0) * 100).toFixed(1)}%</td>
                            <td className="text-right font-mono">{((row.recall || 0) * 100).toFixed(1)}%</td>
                            <td className="text-right font-mono">{((row.f1 || 0) * 100).toFixed(1)}%</td>
                            <td className={`text-right font-mono ${(row.total_return ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {row.total_return != null ? `${row.total_return >= 0 ? '+' : ''}${row.total_return.toFixed(2)}%` : '—'}
                            </td>
                            <td className="text-right font-mono text-rose-400">
                              {row.max_drawdown != null ? `-${Math.abs(row.max_drawdown).toFixed(2)}%` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="text-[10px] text-muted-foreground">{comparison.disclaimer}</p>
                  </div>
                )}

                {backtest && (
                  <div className="rounded-lg border border-border bg-card p-3 space-y-3">
                    <div className="flex flex-wrap justify-between gap-2">
                      <strong className="font-mono">{backtest.strategy_name}</strong>
                      <span className="text-[10px] text-muted-foreground">{backtest.backtest_id.slice(0, 8)}…</span>
                    </div>

                    {backtest.persisted === false && (
                      <div className="rounded border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs text-amber-300 flex items-center gap-2">
                        <AlertTriangle className="size-4 shrink-0" />
                        <span>Simulation completed, but persistence to database failed: {backtest.persist_error || 'Database write error'}. This run was not saved to history.</span>
                      </div>
                    )}

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="rounded bg-muted/30 p-2">
                        Final <strong className="block font-mono">₹{backtest.final_value.toLocaleString('en-IN')}</strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Return{' '}
                        <strong className={`block font-mono ${backtest.total_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {backtest.total_return >= 0 ? '+' : ''}{backtest.total_return.toFixed(2)}%
                        </strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Annual Return{' '}
                        <strong className={`block font-mono ${backtest.annual_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {backtest.annual_return >= 0 ? '+' : ''}{backtest.annual_return.toFixed(2)}%
                        </strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Max DD <strong className="block font-mono text-rose-400">-{Math.abs(backtest.max_drawdown).toFixed(2)}%</strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Win Rate{' '}
                        <strong className="block font-mono">
                          {backtest.win_rate != null ? `${backtest.win_rate.toFixed(1)}%` : '—'}
                        </strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Sharpe Ratio{' '}
                        <strong className="block font-mono">
                          {backtest.sharpe_ratio != null ? backtest.sharpe_ratio.toFixed(2) : '—'}
                        </strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Profit Factor{' '}
                        <strong className="block font-mono">
                          {backtest.profit_factor != null ? backtest.profit_factor.toFixed(2) : '—'}
                        </strong>
                      </div>
                      <div className="rounded bg-muted/30 p-2">
                        Trades <strong className="block font-mono">{backtest.num_trades}</strong>
                      </div>
                    </div>
                    {backtest.equity_curve?.length > 0 && (
                      <div>
                        <p className="text-[11px] text-muted-foreground mb-1">Equity curve (sampled)</p>
                        <div className="flex items-end gap-0.5 h-16">
                          {backtest.equity_curve
                            .filter((_, i, arr) => i % Math.max(1, Math.floor(arr.length / 40)) === 0)
                            .map((pt, idx) => {
                              const values = backtest.equity_curve.map((p) => p.value);
                              const min = Math.min(...values);
                              const max = Math.max(...values);
                              const height = max === min ? 50 : ((pt.value - min) / (max - min)) * 100;
                              return (
                                <div
                                  key={`${pt.date}-${idx}`}
                                  className="flex-1 bg-primary/70 rounded-t"
                                  style={{ height: `${Math.max(8, height)}%` }}
                                  title={`${pt.date}: ₹${pt.value.toFixed(0)}`}
                                />
                              );
                            })}
                        </div>
                      </div>
                    )}
                    <p className="text-[10px] text-muted-foreground">{backtest.disclaimer}</p>
                  </div>
                )}

                {backtestHistory.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="text-[11px] font-medium text-muted-foreground">Recent persisted backtests</p>
                    {backtestHistory.slice(0, 5).map((bt) => (
                      <button
                        key={bt.backtest_id}
                        type="button"
                        onClick={() => setBacktest(bt)}
                        className="w-full text-left rounded border border-border/60 px-2.5 py-2 hover:bg-muted/30"
                      >
                        <div className="flex justify-between gap-2">
                          <span className="font-mono">{bt.symbol}</span>
                          <span className={`font-mono ${bt.total_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {bt.total_return >= 0 ? '+' : ''}{bt.total_return.toFixed(2)}%
                          </span>
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {bt.strategy_name} · {bt.start_date} → {bt.end_date}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-5 space-y-6">
            <Card className="border-border/80 bg-card/60 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Play className="size-4 text-primary" />
                  Live Model Prediction
                </CardTitle>
                <CardDescription className="text-xs">
                  Generate directional forecasts and persist them to prediction history.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-1 text-xs">
                <div className="p-2.5 rounded bg-muted/40 border border-border flex items-center justify-between">
                  <span className="text-muted-foreground">Active Model:</span>
                  <span className="font-mono font-semibold text-primary truncate max-w-[200px]">
                    {selectedModel?.model_id || 'Auto-select Best'}
                  </span>
                </div>

                <div className="space-y-1.5">
                  <label className="font-medium text-foreground/80">Stock Symbol</label>
                  <Input
                    type="text"
                    value={testSymbol}
                    onChange={(e) => setTestSymbol(e.target.value.toUpperCase())}
                    placeholder="e.g. RELIANCE, INFY, TCS..."
                    className="font-mono uppercase text-xs"
                  />
                  <div className="flex flex-wrap gap-1 pt-1">
                    {['RELIANCE', 'INFY', 'TCS', 'HDFCBANK'].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setTestSymbol(s)}
                        className={`text-[10px] font-mono px-1.5 py-0.5 rounded border transition-colors ${
                          testSymbol === s
                            ? 'bg-primary/20 text-primary border-primary/40 font-semibold'
                            : 'bg-muted/40 text-muted-foreground hover:text-foreground border-border/40'
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="font-medium text-foreground/80">Prediction Horizon</label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { days: 1, label: '1 Day' },
                      { days: 5, label: '5 Days' },
                      { days: 20, label: '20 Days' },
                    ].map((h) => (
                      <button
                        key={h.days}
                        type="button"
                        onClick={() => setTestHorizon(h.days)}
                        className={`py-1.5 px-2 rounded border text-center font-medium transition-all ${
                          testHorizon === h.days
                            ? 'bg-primary/15 border-primary text-primary font-semibold'
                            : 'bg-muted/30 border-border/60 text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {h.label}
                      </button>
                    ))}
                  </div>
                </div>

                <Button
                  onClick={handleRunTestPrediction}
                  disabled={!testSymbol.trim() || isPredicting}
                  className="w-full gap-2 font-medium"
                >
                  {isPredicting ? (
                    <>
                      <RefreshCw className="size-3.5 animate-spin" />
                      Running Inference...
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-3.5" />
                      Generate Prediction
                    </>
                  )}
                </Button>

                {predictionError && (
                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                    <strong>Inference Error:</strong> {predictionError}
                  </div>
                )}

                {predictionResult && (
                  <div className="p-3.5 rounded-lg border border-border bg-card space-y-3 mt-3">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-base text-foreground">
                        {predictionResult.symbol}
                      </span>
                      <Badge
                        className={`text-xs px-2 py-0.5 font-semibold ${
                          normalizeClass(predictionResult.predicted_class) === 'Positive'
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : normalizeClass(predictionResult.predicted_class) === 'Negative'
                            ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                        }`}
                      >
                        {normalizeClass(predictionResult.predicted_class) === 'Positive' ? (
                          <ArrowUpRight className="size-3.5 mr-1" />
                        ) : normalizeClass(predictionResult.predicted_class) === 'Negative' ? (
                          <ArrowDownRight className="size-3.5 mr-1" />
                        ) : (
                          <Minus className="size-3.5 mr-1" />
                        )}
                        {normalizeClass(predictionResult.predicted_class)}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Confidence Score:</span>
                      <strong className="text-foreground font-mono">
                        {(predictionResult.confidence * 100).toFixed(1)}%
                      </strong>
                    </div>
                    {predictionResult.probabilities && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[11px] text-muted-foreground block">Class Probabilities:</span>
                        {Object.entries(predictionResult.probabilities).map(([cls, prob]) => (
                          <div key={cls} className="space-y-0.5">
                            <div className="flex justify-between text-[10px]">
                              <span className="capitalize">{cls}</span>
                              <span className="font-mono">{(prob * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{ width: `${prob * 100}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="pt-2 border-t border-border/40 text-[10px] text-muted-foreground flex justify-between">
                      <span>As of: {predictionResult.as_of_date || 'Latest Market Bar'}</span>
                      <span>Horizon: {predictionResult.horizon_days}D</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {selectedModel && (
              <Card className="border-border/80 bg-card/60 shadow-sm p-4 text-xs space-y-2.5">
                <h4 className="font-semibold text-foreground flex items-center gap-1.5">
                  <Info className="size-3.5 text-primary" />
                  Model Architecture & Features
                </h4>
                <div className="space-y-1 text-muted-foreground">
                  <div>
                    Type:{' '}
                    <strong className="text-foreground capitalize">
                      {selectedModel.model_type.replace('_', ' ')}
                    </strong>
                  </div>
                  <div>
                    Feature Dimension:{' '}
                    <strong className="text-foreground">{selectedModel.feature_count}</strong>
                  </div>
                  <div>
                    Target Classes:{' '}
                    <strong className="text-foreground">{selectedModel.classes.join(', ')}</strong>
                  </div>
                  <div>
                    Model Status:{' '}
                    <Badge variant="outline" className="text-[10px] ml-1">
                      {selectedModel.status}
                    </Badge>
                  </div>
                </div>
              </Card>
            )}

            <Card className="border-border/80 bg-card/60 shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <History className="size-4 text-primary" />
                    Prediction History
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => loadPredictionHistory(testSymbol || undefined, selectedModel?.model_id)}
                    disabled={historyLoading}
                  >
                    <RefreshCw className={`size-3 ${historyLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <CardDescription className="text-xs">
                  Persisted backend predictions (not browser local storage).
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-xs">
                {historyError && (
                  <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">
                    {historyError}
                  </div>
                )}
                {historyLoading ? (
                  <div className="py-8 text-center text-muted-foreground">
                    <RefreshCw className="size-4 animate-spin mx-auto mb-2" />
                    Loading history...
                  </div>
                ) : predictionHistory.length === 0 ? (
                  <div className="py-8 text-center text-muted-foreground">
                    No persisted predictions yet. Generate one above.
                  </div>
                ) : (
                  predictionHistory.map((item) => (
                    <div
                      key={item.prediction_id}
                      className="rounded border border-border/60 px-2.5 py-2 flex items-center justify-between gap-2"
                    >
                      <div>
                        <div className="font-mono font-semibold">{item.symbol}</div>
                        <div className="text-[10px] text-muted-foreground">
                          {normalizeClass(item.predicted_class)} · {(item.confidence * 100).toFixed(1)}% ·{' '}
                          {item.horizon_days}D
                        </div>
                      </div>
                      <div className="text-[10px] text-muted-foreground text-right">
                        <div>{new Date(item.prediction_date).toLocaleString('en-IN')}</div>
                        <div className="font-mono truncate max-w-[120px]">{String(item.model_id ?? '—')}</div>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
