'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Brain,
  Cpu,
  ShieldAlert,
  Sparkles,
  RefreshCw,
  ExternalLink,
  Info,
  AlertTriangle,
  Activity,
  Newspaper,
  BarChart3,
  Building2,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import apiClient, { UnifiedStockIntelligenceResponse } from '@/lib/api-client';

interface UnifiedStockIntelligenceProps {
  symbol: string;
  companyName?: string;
}

function SectionUnavailable({ reason }: { reason?: string | null }) {
  return (
    <div className="rounded border border-border/50 bg-muted/20 p-3 text-xs text-muted-foreground">
      <div className="flex items-start gap-2">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        <span>{reason || 'Data unavailable for this section.'}</span>
      </div>
    </div>
  );
}

function formatINR(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '—';
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function formatPct(value?: number | null, digits = 2) {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(digits)}%`;
}

function normalizeClass(label?: string | null) {
  if (!label) return 'Neutral';
  const lower = label.toLowerCase();
  if (lower === 'positive') return 'Positive';
  if (lower === 'negative') return 'Negative';
  if (lower === 'neutral') return 'Neutral';
  return label;
}

export function UnifiedStockIntelligence({ symbol, companyName }: UnifiedStockIntelligenceProps) {
  const [data, setData] = useState<UnifiedStockIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getUnifiedStockIntelligence(symbol);
      if (res.status === 'success' && res.data) {
        setData(res.data);
      } else {
        setData(null);
        setError(res.error || 'Failed to load unified stock intelligence.');
      }
    } catch (err: any) {
      setData(null);
      setError(err?.message || 'Error communicating with intelligence API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [symbol]);

  const market = data?.market_intelligence;
  const technical = data?.technical_intelligence;
  const fundamental = data?.fundamental_intelligence;
  const news = data?.news_intelligence;
  const ml = data?.ml_intelligence;
  const risk = data?.risk_intelligence;
  const synthesis = data?.ai_synthesis;
  const agentInsights = data?.agent_insights;
  const predicted = normalizeClass(ml?.predicted_class);

  return (
    <div className="space-y-4">
      <Card className="border-border/80 bg-card/80 shadow-none overflow-hidden">
        <CardHeader className="pb-3 border-b border-border/40 bg-muted/20">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-primary/10 border border-primary/20 text-primary">
                <Brain className="size-4" />
              </div>
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  Unified AI Stock Intelligence
                  <Badge variant="outline" className="text-[10px] text-primary border-primary/30 font-mono">
                    LIVE
                  </Badge>
                </CardTitle>
                <CardDescription className="text-xs">
                  Consolidated market, technical, fundamental, news, ML and risk intelligence for{' '}
                  {companyName || symbol}.
                </CardDescription>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="xs"
                className="gap-1.5 text-xs"
                onClick={load}
                disabled={loading}
              >
                <RefreshCw className={`size-3 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Link href="/agents">
                <Button variant="outline" size="xs" className="gap-1.5 text-xs">
                  <Sparkles className="size-3 text-cyan-400" />
                  Multi-Agent Workspace
                  <ExternalLink className="size-3" />
                </Button>
              </Link>
              <Link href="/research">
                <Button variant="outline" size="xs" className="gap-1.5 text-xs">
                  <Activity className="size-3 text-emerald-400" />
                  Research Hub
                  <ExternalLink className="size-3" />
                </Button>
              </Link>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-5 space-y-5">
          {loading && (
            <div className="py-10 text-center text-xs text-muted-foreground space-y-2">
              <RefreshCw className="size-5 animate-spin text-primary mx-auto" />
              <p>Loading unified intelligence for {symbol}...</p>
            </div>
          )}

          {!loading && error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300 flex items-start gap-3">
              <AlertTriangle className="size-4 mt-0.5 shrink-0" />
              <div className="space-y-2">
                <p>{error}</p>
                <Button variant="outline" size="xs" onClick={load}>
                  Retry
                </Button>
              </div>
            </div>
          )}

          {!loading && data && (
            <>
              {(data.warnings?.length || 0) > 0 && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                  <strong className="block mb-1">Data notices</strong>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {data.warnings!.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Overview */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                  <span className="text-muted-foreground">Company</span>
                  <p className="mt-1 font-semibold text-foreground">{data.company_name}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {data.sector || '—'} · {data.exchange || '—'}
                  </p>
                </div>
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                  <span className="text-muted-foreground">Last Close</span>
                  <p className="mt-1 font-semibold font-mono text-foreground">
                    {market?.status === 'available' ? formatINR(market.current_price) : '—'}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {market?.status === 'available'
                      ? `${formatPct(market.day_change_pct)} · ${market.as_of_date || '—'}`
                      : market?.reason || 'Unavailable'}
                  </p>
                </div>
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                  <span className="text-muted-foreground">Freshness</span>
                  <p className="mt-1 font-semibold capitalize text-foreground">
                    {market?.status === 'available' ? market.freshness || '—' : 'Unavailable'}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Source: {market?.source || '—'}
                  </p>
                </div>
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
                  <span className="text-muted-foreground">Generated</span>
                  <p className="mt-1 font-semibold text-foreground text-[11px]">
                    {new Date(data.generated_at).toLocaleString('en-IN')}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Technical */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="size-4 text-cyan-400" />
                      Technical Analysis
                    </div>
                    {technical?.freshness && (
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {technical.freshness}
                      </Badge>
                    )}
                  </div>
                  {technical?.status !== 'available' ? (
                    <SectionUnavailable reason={technical?.reason} />
                  ) : (
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Trend</span>
                        <span className="font-medium">
                          {technical.trend?.classification || '—'}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="rounded bg-card border border-border p-2">
                          RSI-14: <strong className="font-mono">{technical.rsi_14 ?? '—'}</strong>
                        </div>
                        <div className="rounded bg-card border border-border p-2">
                          ATR-14: <strong className="font-mono">{technical.atr_14 ?? '—'}</strong>
                        </div>
                        <div className="rounded bg-card border border-border p-2">
                          EMA-20: <strong className="font-mono">{formatINR(technical.ema_20)}</strong>
                        </div>
                        <div className="rounded bg-card border border-border p-2">
                          EMA-50: <strong className="font-mono">{formatINR(technical.ema_50)}</strong>
                        </div>
                        <div className="rounded bg-card border border-border p-2">
                          Vol: <strong className="font-mono">{formatPct(technical.annualized_volatility_pct)}</strong>
                        </div>
                        <div className="rounded bg-card border border-border p-2">
                          Max DD: <strong className="font-mono">{formatPct(technical.max_drawdown_pct)}</strong>
                        </div>
                      </div>
                      {technical.trend?.explanation && (
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          {technical.trend.explanation}
                        </p>
                      )}
                      <div className="flex justify-between items-center text-[10px] text-muted-foreground pt-1 border-t border-border/40">
                        <span>Source: {technical.source || 'daily_market_data'}</span>
                        <span>Window: {technical.data_window_days ?? 0} days</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Fundamentals */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold">
                    <Building2 className="size-4 text-emerald-400" />
                    Fundamental Analysis
                  </div>
                  {fundamental?.status !== 'available' ? (
                    <SectionUnavailable reason={fundamental?.reason} />
                  ) : (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded bg-card border border-border p-2">
                        P/E: <strong className="font-mono">{fundamental.pe_ratio ?? '—'}</strong>
                      </div>
                      <div className="rounded bg-card border border-border p-2">
                        ROE: <strong className="font-mono">{fundamental.roe ?? '—'}</strong>
                      </div>
                      <div className="rounded bg-card border border-border p-2">
                        Margin: <strong className="font-mono">{fundamental.profit_margin ?? '—'}</strong>
                      </div>
                      <div className="rounded bg-card border border-border p-2">
                        D/E: <strong className="font-mono">{fundamental.debt_to_equity ?? '—'}</strong>
                      </div>
                      <div className="col-span-2 text-[11px] text-muted-foreground">
                        Period end: {fundamental.period_end || '—'}
                      </div>
                    </div>
                  )}
                </div>

                {/* News */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold">
                    <Newspaper className="size-4 text-amber-400" />
                    News & Sentiment
                  </div>
                  {news?.status !== 'available' ? (
                    <SectionUnavailable reason={news?.reason} />
                  ) : (
                    <div className="space-y-2 text-xs">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline" className="text-[10px]">
                          +{news.positive ?? 0} positive
                        </Badge>
                        <Badge variant="outline" className="text-[10px]">
                          -{news.negative ?? 0} negative
                        </Badge>
                        <Badge variant="outline" className="text-[10px]">
                          ~{news.neutral ?? 0} neutral
                        </Badge>
                        <span className="text-muted-foreground font-mono">
                          avg {news.average_sentiment_score ?? '—'}
                        </span>
                      </div>
                      <ul className="space-y-1.5">
                        {(news.latest_articles || []).slice(0, 3).map((article: any, idx: number) => (
                          <li key={`${article.title}-${idx}`} className="rounded bg-card border border-border p-2">
                            <p className="font-medium text-foreground line-clamp-2">{article.title}</p>
                            <p className="text-[10px] text-muted-foreground mt-1">
                              {article.source || 'Source n/a'} · {article.sentiment || 'n/a'}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* ML */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold">
                    <Cpu className="size-4 text-purple-400" />
                    ML Prediction
                  </div>
                  {ml?.status !== 'available' ? (
                    <SectionUnavailable reason={ml?.reason} />
                  ) : (
                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between rounded bg-card border border-border p-2.5">
                        <Badge
                          className={`text-xs font-semibold ${
                            predicted === 'Positive'
                              ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                              : predicted === 'Negative'
                              ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                              : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                          }`}
                        >
                          {predicted}
                        </Badge>
                        <span className="font-mono">
                          {((ml.confidence || 0) * 100).toFixed(1)}% confidence
                        </span>
                      </div>
                      {ml.probabilities && (
                        <div className="space-y-1">
                          {Object.entries(ml.probabilities as Record<string, number>).map(([cls, prob]) => (
                            <div key={cls} className="space-y-0.5">
                              <div className="flex justify-between text-[10px]">
                                <span className="capitalize">{cls}</span>
                                <span className="font-mono">{(prob * 100).toFixed(1)}%</span>
                              </div>
                              <div className="w-full bg-muted/60 rounded-full h-1.5 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-primary"
                                  style={{ width: `${Math.max(0, Math.min(100, prob * 100))}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      <p className="text-[10px] text-muted-foreground">
                        Model: {ml.model_id} · Horizon: {ml.horizon_days}D · As of: {ml.as_of_date || '—'}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Risk + AI synthesis */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold">
                    <ShieldAlert className="size-4 text-rose-400" />
                    Risk Assessment
                  </div>
                  {risk?.status !== 'available' ? (
                    <SectionUnavailable reason={risk?.reason} />
                  ) : (
                    <div className="space-y-2 text-xs">
                      <div className="grid grid-cols-2 gap-2">
                        <div className="rounded bg-card border border-border p-2.5">
                          <span className="text-[10px] text-muted-foreground block">Volatility Profile</span>
                          <span className="font-semibold">{risk.volatility_profile || '—'}</span>
                          <span className="block text-[10px] font-mono text-cyan-400 mt-0.5">
                            {formatPct(risk.annualized_volatility_pct)} pa
                          </span>
                        </div>
                        <div className="rounded bg-card border border-border p-2.5">
                          <span className="text-[10px] text-muted-foreground block">Max Drawdown</span>
                          <span className="font-semibold font-mono">{formatPct(risk.max_drawdown_pct)}</span>
                          <span className="block text-[10px] text-muted-foreground mt-0.5">
                            ATR-14: {risk.atr_14 ?? '—'}
                          </span>
                        </div>
                      </div>
                      {(risk.warnings || []).length > 0 && (
                        <ul className="text-[11px] text-amber-200 space-y-1">
                          {risk.warnings.map((w: string) => (
                            <li key={w}>• {w}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>

                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold">
                    <Sparkles className="size-4 text-primary" />
                    Evidence-based AI Explanation
                  </div>
                  {synthesis?.status !== 'available' ? (
                    <SectionUnavailable reason={synthesis?.reason} />
                  ) : (
                    <div className="space-y-2 text-xs">
                      <p className="text-muted-foreground leading-relaxed">{synthesis.synthesis}</p>
                      <p className="text-[10px] text-muted-foreground/80">
                        {synthesis.disclaimer || data.disclaimer}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {agentInsights?.status === 'available' && (
                <div className="rounded-lg border border-border/60 bg-muted/20 p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <div className="flex items-center gap-2">
                      <Activity className="size-4 text-emerald-400" />
                      Research Insights
                    </div>
                    <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30">
                      Persisted Reports
                    </Badge>
                  </div>
                  <ul className="space-y-2 text-xs">
                    {(agentInsights.insights || []).map((insight: any) => (
                      <li key={insight.report_id} className="rounded bg-card border border-border p-2.5">
                        <div className="flex justify-between gap-2 mb-1">
                          <span className="font-medium flex items-center gap-1.5">
                            {insight.report_type}
                            {insight.is_persisted && (
                              <span className="text-[9px] bg-muted px-1 py-0.5 rounded text-muted-foreground">Stored</span>
                            )}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {insight.generated_at
                              ? new Date(insight.generated_at).toLocaleString('en-IN')
                              : ''}
                          </span>
                        </div>
                        <p className="text-muted-foreground line-clamp-3">{insight.excerpt}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="text-[10px] text-muted-foreground border-t border-border/40 pt-3">
                {data.disclaimer}
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
