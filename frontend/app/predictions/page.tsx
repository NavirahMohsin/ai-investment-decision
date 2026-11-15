'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/layout/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ArrowUp, ArrowDown, TrendingUp, AlertCircle, Loader2 } from 'lucide-react';
import { API_URL } from '@/lib/api';

interface PredictionResult {
  symbol: string;
  predicted_class: 'Positive' | 'Negative' | 'Neutral';
  confidence: number;
  probabilities: {
    Positive: number;
    Negative: number;
    Neutral: number;
  };
  horizon_days: number;
  as_of_date: string;
  model_id: string;
  prediction_id: string;
  current_price: number | null;
  timestamp: string;
}

interface BatchPredictionResponse {
  predictions: PredictionResult[];
  summary: {
    total_predictions: number;
    positive_count: number;
    negative_count: number;
    neutral_count: number;
    average_confidence: number;
    min_confidence: number;
    max_confidence: number;
    generated_at: string;
  };
}

interface AvailableModel {
  model_id: string;
  model_type: string;
  version: string;
  accuracy?: number;
  f1_score?: number;
  status: string;
}

export default function PredictionsPage() {
  const [symbol, setSymbol] = useState('RELIANCE');
  const [symbols, setSymbols] = useState('RELIANCE,TCS,HDFCBANK');
  const [mode, setMode] = useState<'single' | 'batch'>('single');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResult | BatchPredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [horizon, setHorizon] = useState(1);
  const [modelLoading, setModelLoading] = useState(true);
  const [noModelsAvailable, setNoModelsAvailable] = useState(false);

  // Load available models on mount
  const loadModels = async () => {
    setModelLoading(true);
    setNoModelsAvailable(false);
    try {
      const response = await fetch(`${API_URL}/api/v1/predictions/models`, {
        cache: 'no-store',
      });
      if (response.ok) {
        const data = await response.json();
        const modelList = data.models || [];
        if (modelList.length > 0) {
          setModels(modelList);
          setSelectedModel(modelList[0].model_id);
        } else {
          setNoModelsAvailable(true);
          setError('No trained models are currently available. Please train a model first.');
        }
      } else {
        setNoModelsAvailable(true);
        setError('Unable to load available models from the server.');
      }
    } catch (err) {
      console.error('Failed to load models:', err);
      setNoModelsAvailable(true);
      setError('Failed to connect to the prediction service.');
    } finally {
      setModelLoading(false);
    }
  };

  // Load models when component mounts
  useEffect(() => {
    loadModels();
  }, []);

  const makePrediction = async () => {
    if (!selectedModel) {
      setError('Please select a model');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let response;
      const apiUrl = `${API_URL}/api/v1/predictions`;

      if (mode === 'single') {
        response = await fetch(`${apiUrl}/predict`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol: symbol.toUpperCase(),
            model_id: selectedModel,
            model_version: 'latest',
            horizon_days: horizon,
            include_features: false,
          }),
        });
      } else {
        const symbolList = symbols
          .split(',')
          .map((s) => s.trim().toUpperCase())
          .filter((s) => s);

        if (symbolList.length === 0) {
          throw new Error('Please enter at least one valid stock symbol');
        }

        response = await fetch(`${apiUrl}/predict/batch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbols: symbolList,
            model_id: selectedModel,
            model_version: 'latest',
            horizon_days: horizon,
          }),
        });
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `API error: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get prediction');
    } finally {
      setLoading(false);
    }
  };

  const getIcon = (prediction: string) => {
    if (prediction === 'Positive') return <ArrowUp className="w-5 h-5 text-green-500" />;
    if (prediction === 'Negative') return <ArrowDown className="w-5 h-5 text-red-500" />;
    return <TrendingUp className="w-5 h-5 text-gray-500" />;
  };

  const getColor = (prediction: string) => {
    if (prediction === 'Positive') return 'bg-green-50 border-green-200';
    if (prediction === 'Negative') return 'bg-red-50 border-red-200';
    return 'bg-gray-50 border-gray-200';
  };

  const formatPrice = (price: number | null): string => {
    if (price === null || price === undefined) return '₹--';
    return `₹${price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatDate = (dateStr: string): string => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const isBatchResult = (r: any): r is BatchPredictionResponse => 'summary' in r;

  return (
    <DashboardLayout title="AI Price Predictions">
      <div className="space-y-6">
        {/* Controls */}
        <Card>
          <CardHeader>
            <CardTitle>Prediction Settings</CardTitle>
            <CardDescription>Configure your prediction request</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Model Loading State */}
            {modelLoading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Loading available models...
              </div>
            )}

            {/* No Models Available */}
            {!modelLoading && noModelsAvailable && (
              <div className="flex items-start gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-3">
                <AlertCircle className="size-5 flex-shrink-0 text-yellow-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-yellow-800">No models available</p>
                  <p className="text-sm text-yellow-700 mt-1">
                    No trained models are currently available. Please train a model in the Models section first.
                  </p>
                </div>
              </div>
            )}

            {!modelLoading && !noModelsAvailable && (
              <>
                {/* Mode Selection */}
                <div>
                  <label className="text-sm font-medium">Prediction Mode</label>
                  <div className="flex gap-2 mt-2">
                    <Button
                      variant={mode === 'single' ? 'default' : 'outline'}
                      onClick={() => setMode('single')}
                    >
                      Single Stock
                    </Button>
                    <Button
                      variant={mode === 'batch' ? 'default' : 'outline'}
                      onClick={() => setMode('batch')}
                    >
                      Batch Stocks
                    </Button>
                  </div>
                </div>

                {/* Model Selection */}
                {models.length > 0 && (
                  <div>
                    <label className="text-sm font-medium">Model</label>
                    <select
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-md text-sm bg-white"
                    >
                      {models.map((m) => (
                        <option key={`${m.model_id}_${m.version}`} value={m.model_id}>
                          {m.model_id} ({m.model_type}) - v{m.version}
                          {m.accuracy ? ` - Accuracy: ${(m.accuracy * 100).toFixed(1)}%` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Horizon Selection */}
                <div>
                  <label className="text-sm font-medium">Prediction Horizon</label>
                  <div className="flex gap-2 mt-2">
                    {[1, 5, 20].map((h) => (
                      <Button
                        key={h}
                        variant={horizon === h ? 'default' : 'outline'}
                        onClick={() => setHorizon(h)}
                        size="sm"
                      >
                        {h} days
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Symbol Input */}
                {mode === 'single' ? (
                  <div>
                    <label className="text-sm font-medium">Stock Symbol</label>
                    <Input
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                      placeholder="e.g., RELIANCE"
                      className="mt-2"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="text-sm font-medium">Stock Symbols (comma-separated)</label>
                    <Input
                      value={symbols}
                      onChange={(e) => setSymbols(e.target.value.toUpperCase())}
                      placeholder="e.g., RELIANCE,TCS,HDFCBANK"
                      className="mt-2"
                    />
                  </div>
                )}

                {/* Error Display */}
                {error && (
                  <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3">
                    <AlertCircle className="size-5 flex-shrink-0 text-red-600 mt-0.5" />
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}

                {/* Submit Button */}
                <Button onClick={makePrediction} disabled={loading} className="w-full">
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Getting Predictions...
                    </>
                  ) : (
                    'Get Predictions'
                  )}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {isBatchResult(result) ? (
              <>
                {/* Batch Summary */}
                <Card>
                  <CardHeader>
                    <CardTitle>Prediction Summary</CardTitle>
                    <CardDescription>Generated on {formatDate(result.summary.generated_at)}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600">
                          {result.summary.positive_count}
                        </div>
                        <div className="text-sm text-muted-foreground">Positive</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-red-600">
                          {result.summary.negative_count}
                        </div>
                        <div className="text-sm text-muted-foreground">Negative</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-gray-600">
                          {result.summary.neutral_count}
                        </div>
                        <div className="text-sm text-muted-foreground">Neutral</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold">
                          {(result.summary.average_confidence * 100).toFixed(1)}%
                        </div>
                        <div className="text-sm text-muted-foreground">Avg Confidence</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Individual Predictions */}
                <div className="space-y-2">
                  {result.predictions.map((pred) => (
                    <Card key={pred.symbol} className={`border ${getColor(pred.predicted_class)}`}>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            {getIcon(pred.predicted_class)}
                            <div>
                              <h3 className="font-semibold text-lg">{pred.symbol}</h3>
                              <p className="text-sm text-muted-foreground">
                                {pred.predicted_class} • {(pred.confidence * 100).toFixed(1)}% confidence
                              </p>
                              {pred.current_price && (
                                <p className="text-sm text-muted-foreground">
                                  Current: {formatPrice(pred.current_price)}
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-muted-foreground mb-2">Probabilities:</div>
                            <div className="space-y-1 text-sm">
                              <div className="text-green-600">
                                Pos: {(pred.probabilities.Positive * 100).toFixed(0)}%
                              </div>
                              <div className="text-red-600">
                                Neg: {(pred.probabilities.Negative * 100).toFixed(0)}%
                              </div>
                              <div className="text-gray-600">
                                Neu: {(pred.probabilities.Neutral * 100).toFixed(0)}%
                              </div>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </>
            ) : (
              /* Single Prediction */
              <Card className={`border ${getColor((result as PredictionResult).predicted_class)}`}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {getIcon((result as PredictionResult).predicted_class)}
                    {result.symbol} Prediction
                  </CardTitle>
                  <CardDescription>
                    {result.horizon_days}-day outlook • Model: {result.model_id} • {formatDate(result.timestamp)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Main Prediction */}
                  <div className="text-center">
                    <div className="text-4xl font-bold mb-2">{result.predicted_class}</div>
                    <div className="text-2xl font-semibold text-muted-foreground">
                      {(result.confidence * 100).toFixed(1)}% confidence
                    </div>
                  </div>

                  {/* Probabilities Chart */}
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-sm font-medium">Positive</span>
                        <span className="text-sm font-semibold">{(result.probabilities.Positive * 100).toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-500 h-2 rounded-full"
                          style={{ width: `${result.probabilities.Positive * 100}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-sm font-medium">Negative</span>
                        <span className="text-sm font-semibold">{(result.probabilities.Negative * 100).toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-red-500 h-2 rounded-full"
                          style={{ width: `${result.probabilities.Negative * 100}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between mb-1">
                        <span className="text-sm font-medium">Neutral</span>
                        <span className="text-sm font-semibold">{(result.probabilities.Neutral * 100).toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-gray-500 h-2 rounded-full"
                          style={{ width: `${result.probabilities.Neutral * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="bg-gray-50 rounded-lg p-3 text-sm space-y-1">
                    {result.current_price && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Current Price:</span>
                        <span className="font-medium">{formatPrice(result.current_price)}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Data Date:</span>
                      <span className="font-medium">{formatDate(result.as_of_date)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Prediction ID:</span>
                      <span className="font-mono text-xs">{result.prediction_id.slice(0, 8)}...</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model Version:</span>
                      <span className="font-medium">{result.model_id}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Info Card - shown when no results */}
        {!result && !noModelsAvailable && (
          <Card>
            <CardHeader>
              <CardTitle>About AI Predictions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Our machine learning models analyze historical price data, technical indicators, and market patterns to
                predict stock price movements.
              </p>
              <div>
                <p className="font-medium mb-1">Prediction Classes:</p>
                <ul className="space-y-1 text-muted-foreground">
                  <li>• <span className="text-green-600">Positive</span>: Expected price increase</li>
                  <li>• <span className="text-red-600">Negative</span>: Expected price decrease</li>
                  <li>• <span className="text-gray-600">Neutral</span>: No significant change expected</li>
                </ul>
              </div>
              <p>
                <strong>Confidence:</strong> How confident the model is in its prediction (0-100%)
              </p>
              <p>
                <strong>Horizon:</strong> Time period for the prediction (1, 5, or 20 days)
              </p>
              <p className="text-muted-foreground italic">
                ⚠️ These are AI-generated predictions for research purposes only. Not financial advice. Always do your own
                research before making investment decisions.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
