'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Cpu,
  TrendingUp,
  Award,
  Calendar,
  CheckCircle2,
  BarChart3,
  Search,
  RefreshCw,
  AlertTriangle,
  Play,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Sparkles,
  SlidersHorizontal,
  Info,
  Check,
  Zap,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { fetchCompanies, Company } from '@/lib/api';
import apiClient, { ModelMetadata, PredictionResult } from '@/lib/api-client';

const MODEL_TYPE_BADGES: Record<string, { label: string; color: string }> = {
  xgboost: { label: 'XGBoost', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  lightgbm: { label: 'LightGBM', color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' },
  random_forest: { label: 'Random Forest', color: 'bg-purple-500/10 text-purple-400 border-purple-500/30' },
  logistic_regression: { label: 'Logistic Regression', color: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
};

export default function ModelsEvaluationPage() {
  const [models, setModels] = useState<ModelMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<ModelMetadata | null>(null);

  // Live Inference Test Panel state
  const [companies, setCompanies] = useState<Company[]>([]);
  const [testSymbol, setTestSymbol] = useState('RELIANCE');
  const [testHorizon, setTestHorizon] = useState<number>(1);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionResult, setPredictionResult] = useState<PredictionResult | null>(null);
  const [predictionError, setPredictionError] = useState<string | null>(null);

  // Prediction history
  const [predictionHistory, setPredictionHistory] = useState<
    Array<{
      id: string;
      symbol: string;
      model_id: string;
      horizon: number;
      predicted_class: string;
      confidence: number;
      timestamp: string;
    }>
  >([]);

  // Fetch models
  const loadModels = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.listPredictionModels();
      if (res.status === 'success' && res.data) {
        setModels(res.data.models || []);
        if (res.data.models && res.data.models.length > 0) {
          // Default selection to model with highest accuracy
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

  useEffect(() => {
    loadModels();
    fetchCompanies()
      .then(setCompanies)
      .catch((e) => console.warn('Could not load companies for test:', e));

    try {
      const stored = localStorage.getItem('arthai_model_prediction_history');
      if (stored) {
        setPredictionHistory(JSON.parse(stored));
      }
    } catch (e) {
      console.warn('Could not load prediction history:', e);
    }
  }, []);

  // Filtered models list
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

  // Aggregate stats
  const bestAccuracy = useMemo(() => {
    if (models.length === 0) return 0;
    return Math.max(...models.map((m) => m.accuracy || 0));
  }, [models]);

  const bestF1 = useMemo(() => {
    if (models.length === 0) return 0;
    return Math.max(...models.map((m) => m.f1_score || 0));
  }, [models]);

  // Run live prediction test
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
        const newEntry = {
          id: `${Date.now()}_${sym}`,
          symbol: sym,
          model_id: res.data.model_id || selectedModel?.model_id || 'latest',
          horizon: testHorizon,
          predicted_class: res.data.predicted_class,
          confidence: res.data.confidence,
          timestamp: new Date().toISOString(),
        };
        setPredictionHistory((prev) => {
          const updated = [newEntry, ...prev.slice(0, 19)];
          try {
            localStorage.setItem('arthai_model_prediction_history', JSON.stringify(updated));
          } catch (e) {
            // ignore
          }
          return updated;
        });
      } else {
        setPredictionError(res.error || 'Prediction generation failed.');
      }
    } catch (err: any) {
      setPredictionError(err?.message || 'Error invoking model prediction.');
    } finally {
      setIsPredicting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      {/* Top Banner */}
      <div className="border-b border-border/60 bg-card/40 backdrop-blur px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 font-semibold text-primary">
              <Cpu className="size-4" />
              ArthAI ML Model Registry & Evaluation Benchmarks
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span className="text-muted-foreground">ModelServer Infrastructure</span>
          </div>

          <div className="flex items-center gap-4 text-muted-foreground">
            <span>
              Registered Models: <strong className="text-foreground">{models.length}</strong>
            </span>
            <Separator orientation="vertical" className="h-4" />
            <span>
              Best Accuracy: <strong className="text-emerald-400 font-mono">{(bestAccuracy * 100).toFixed(1)}%</strong>
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6">
        {/* Workspace Title */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2.5">
              Model Evaluation & Benchmarking
              <Badge variant="outline" className="text-purple-400 border-purple-500/30 font-mono text-[10px]">
                PRODUCTION ARTIFACTS
              </Badge>
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Inspect trained directional classifiers, evaluate accuracy/F1 benchmarks, compare algorithms, and run
              live inference tests.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={loadModels}
            disabled={loading}
            className="self-start md:self-auto gap-1.5 text-xs border-border/80"
          >
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Models
          </Button>
        </div>

        {/* Error Alert */}
        {errorMsg && (
          <div className="mb-6 rounded-lg bg-rose-500/10 border border-rose-500/30 p-4 flex items-start gap-3 text-rose-300 text-sm">
            <AlertTriangle className="size-5 shrink-0 text-rose-400 mt-0.5" />
            <div className="flex-1">
              <strong className="font-semibold block mb-0.5">Model Server Notice</strong>
              {errorMsg}
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-xs text-rose-400/80 hover:text-rose-300 underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Benchmark Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
          <Card className="border-border/80 bg-card/60 backdrop-blur p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Available Models</span>
              <Cpu className="size-4 text-primary" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-foreground">{models.length}</div>
            <p className="text-[11px] text-muted-foreground mt-1">LightGBM, XGBoost, RF, LR</p>
          </Card>

          <Card className="border-border/80 bg-card/60 backdrop-blur p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Top Benchmark Accuracy</span>
              <Award className="size-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-emerald-400">
              {(bestAccuracy * 100).toFixed(1)}%
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">Directional classification</p>
          </Card>

          <Card className="border-border/80 bg-card/60 backdrop-blur p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Top F1-Score</span>
              <TrendingUp className="size-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-cyan-400">
              {(bestF1 * 100).toFixed(1)}%
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">Multi-class weighted average</p>
          </Card>

          <Card className="border-border/80 bg-card/60 backdrop-blur p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-medium">Prediction Horizons</span>
              <Calendar className="size-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold mt-2 font-mono text-purple-400">1D, 5D, 20D</div>
            <p className="text-[11px] text-muted-foreground mt-1">Forward-looking target days</p>
          </Card>
        </div>

        {/* WORKSPACE MAIN: Model Registry & Live Inference Tester */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT: Model Registry List & Comparison (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Layers className="size-4 text-primary" />
                      Model Catalog & Benchmarks
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Select a model to view architecture details and test predictions.
                    </CardDescription>
                  </div>

                  {/* Filter chips */}
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

                {/* Search input */}
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
                    <p>Loading model registry from disk...</p>
                  </div>
                ) : filteredModels.length === 0 ? (
                  <div className="py-12 text-center text-xs text-muted-foreground space-y-2">
                    <Cpu className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-foreground font-medium">No models match criteria</p>
                    <p>Adjust your filter or ensure model files exist in backend/models.</p>
                  </div>
                ) : (
                  filteredModels.map((m) => {
                    const isSelected = selectedModel?.model_id === m.model_id;
                    const badgeInfo = MODEL_TYPE_BADGES[m.model_type.toLowerCase()] || {
                      label: m.model_type,
                      color: 'bg-muted text-muted-foreground',
                    };

                    return (
                      <div
                        key={m.model_id}
                        onClick={() => setSelectedModel(m)}
                        className={`p-3 rounded-lg border transition-all cursor-pointer text-xs ${
                          isSelected
                            ? 'bg-primary/5 border-primary shadow-xs ring-1 ring-primary/30'
                            : 'bg-card border-border hover:bg-muted/30'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-semibold text-foreground text-xs">{m.model_id}</span>
                            <Badge variant="outline" className={`text-[10px] scale-90 ${badgeInfo.color}`}>
                              {badgeInfo.label}
                            </Badge>
                          </div>

                          <div className="flex items-center gap-3 font-mono text-[11px]">
                            {m.accuracy !== null && m.accuracy !== undefined && (
                              <span className="text-emerald-400">
                                Acc: <strong>{(m.accuracy * 100).toFixed(1)}%</strong>
                              </span>
                            )}
                            {m.f1_score !== null && m.f1_score !== undefined && (
                              <span className="text-cyan-400">
                                F1: <strong>{(m.f1_score * 100).toFixed(1)}%</strong>
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
                          <div className="flex items-center gap-3">
                            <span>
                              Version: <strong className="text-foreground">{m.version}</strong>
                            </span>
                            <span>•</span>
                            <span>
                              Features: <strong className="text-foreground">{m.feature_count}</strong>
                            </span>
                            <span>•</span>
                            <span>
                              Classes: <strong className="text-foreground">{m.classes.join(', ')}</strong>
                            </span>
                          </div>

                          {m.created_at && (
                            <span className="text-[10px]">
                              {new Date(m.created_at).toLocaleDateString('en-IN', {
                                day: '2-digit',
                                month: 'short',
                                year: 'numeric',
                              })}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>
          </div>

          {/* RIGHT: Selected Model Details & Live Inference Panel (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            {/* Live Inference Tester */}
            <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Play className="size-4 text-primary" />
                  Live Model Prediction
                </CardTitle>
                <CardDescription className="text-xs">
                  Generate directional stock forecasts using the selected trained model.
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-1 text-xs">
                {/* Active Model Indicator */}
                <div className="p-2.5 rounded bg-muted/40 border border-border flex items-center justify-between">
                  <span className="text-muted-foreground">Active Model:</span>
                  <span className="font-mono font-semibold text-primary truncate max-w-[200px]">
                    {selectedModel?.model_id || 'Auto-select Best'}
                  </span>
                </div>

                {/* Test Symbol Input */}
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

                {/* Horizon Selector */}
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

                {/* Predict Button */}
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

                {/* Prediction Result Display */}
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
                          predictionResult.predicted_class === 'Positive'
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                            : predictionResult.predicted_class === 'Negative'
                            ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                        }`}
                      >
                        {predictionResult.predicted_class === 'Positive' ? (
                          <ArrowUpRight className="size-3.5 mr-1" />
                        ) : predictionResult.predicted_class === 'Negative' ? (
                          <ArrowDownRight className="size-3.5 mr-1" />
                        ) : (
                          <Minus className="size-3.5 mr-1" />
                        )}
                        {predictionResult.predicted_class}
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Confidence Score:</span>
                      <strong className="text-foreground font-mono">
                        {(predictionResult.confidence * 100).toFixed(1)}%
                      </strong>
                    </div>

                    {/* Probability Breakdown Bars */}
                    {predictionResult.probabilities && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[11px] text-muted-foreground block">Class Probabilities:</span>
                        {Object.entries(predictionResult.probabilities).map(([cls, prob]) => (
                          <div key={cls} className="space-y-0.5">
                            <div className="flex justify-between text-[10px]">
                              <span>{cls}</span>
                              <span className="font-mono">{(prob * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  cls === 'Positive'
                                    ? 'bg-emerald-500'
                                    : cls === 'Negative'
                                    ? 'bg-rose-500'
                                    : 'bg-amber-500'
                                }`}
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

            {/* Architecture Card */}
            {selectedModel && (
              <Card className="border-border/80 bg-card/60 backdrop-blur shadow-sm p-4 text-xs space-y-2.5">
                <h4 className="font-semibold text-foreground flex items-center gap-1.5">
                  <Info className="size-3.5 text-primary" />
                  Model Architecture & Features
                </h4>
                <div className="space-y-1 text-muted-foreground">
                  <div>
                    Type: <strong className="text-foreground capitalize">{selectedModel.model_type.replace('_', ' ')}</strong>
                  </div>
                  <div>
                    Feature Dimension:{' '}
                    <strong className="text-foreground">{selectedModel.feature_count} technical & momentum signals</strong>
                  </div>
                  <div>
                    Target Classes: <strong className="text-foreground">{selectedModel.classes.join(', ')}</strong>
                  </div>
                  <div>
                    Model Status: <Badge variant="outline" className="text-[10px] ml-1">{selectedModel.status}</Badge>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
