"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleAlert, Database, RefreshCw } from "lucide-react";
import {
  fetchFinancialStatements,
  fetchFundamentalHistory,
  fetchFundamentals,
  type FinancialStatements,
  type FundamentalHistory,
  type FundamentalsSummary,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function numberValue(value: string | number | null | undefined) {
  return value == null || !Number.isFinite(Number(value)) ? null : Number(value);
}

function displayValue(value: string | number | null | undefined, unit?: string | null) {
  const parsed = numberValue(value);
  if (parsed == null) return "—";
  return `${parsed.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`;
}

function SimpleTrendChart({ history }: { history: FundamentalHistory }) {
  const points = useMemo(() => history.revenue.observations.filter((item) => numberValue(item.value) != null), [history]);
  if (points.length < 2) {
    return <p className="text-sm text-muted-foreground">Not enough reported periods for a chart.</p>;
  }
  const values = points.map((point) => numberValue(point.value) as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const path = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 100;
    const y = 90 - ((value - min) / range) * 75;
    return `${index === 0 ? "M" : "L"} ${x} ${y}`;
  }).join(" ");
  return (
    <div>
      <svg viewBox="0 0 100 100" className="h-40 w-full overflow-visible" role="img" aria-label="Revenue history chart">
        <path d={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-cyan-300" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>{points[0].period_end}</span><span>{points.at(-1)?.period_end}</span>
      </div>
    </div>
  );
}

export function FundamentalsPanel({ symbol }: { symbol: string }) {
  const [summary, setSummary] = useState<FundamentalsSummary | null>(null);
  const [history, setHistory] = useState<FundamentalHistory | null>(null);
  const [statements, setStatements] = useState<FinancialStatements | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    void Promise.all([fetchFundamentals(symbol), fetchFundamentalHistory(symbol), fetchFinancialStatements(symbol)])
      .then(([nextSummary, nextHistory, nextStatements]) => {
        setSummary(nextSummary);
        setHistory(nextHistory);
        setStatements(nextStatements);
      })
      .catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Unable to load fundamentals."))
      .finally(() => setLoading(false));
  }, [symbol]);

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (loading) return <div className="h-96 animate-pulse rounded-xl border border-border/70 bg-card/60" />;
  if (error) {
    return (
      <Card className="border-rose-300/20 bg-rose-300/5 shadow-none">
        <CardContent className="flex flex-col items-center px-6 py-10 text-center">
          <CircleAlert className="size-7 text-rose-300" />
          <p className="mt-3 font-medium">Unable to load company fundamentals</p>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" className="mt-5" onClick={load}><RefreshCw className="size-4" /> Try again</Button>
        </CardContent>
      </Card>
    );
  }
  if (!summary) return <p className="text-sm text-muted-foreground">No fundamental data is available.</p>;

  const ratioGroups = summary.ratios ? Object.entries(summary.ratios).filter(([key]) => !["symbol", "period_type", "calculated_at"].includes(key)) : [];
  return (
    <section className="space-y-5" aria-labelledby="fundamentals-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-sm text-cyan-300">Company fundamentals</p><h3 id="fundamentals-title" className="mt-1 text-xl font-semibold">Financial intelligence</h3></div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground"><Database className="size-4 text-cyan-300" /> Yahoo Finance · {summary.company.data_freshness}</div>
      </div>
      {summary.company.business_summary && <Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-5 text-sm leading-6 text-muted-foreground">{summary.company.business_summary}</CardContent></Card>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summary.highlights.map((highlight) => <Card key={highlight.key} className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-4"><p className="text-xs text-muted-foreground">{highlight.label}</p><p className="mt-2 text-lg font-semibold">{displayValue(highlight.value, highlight.unit)}</p><p className="mt-1 text-[11px] text-muted-foreground">{highlight.origin === "unavailable" ? "Not reported" : highlight.period_end ?? "Latest available"}</p></CardContent></Card>)}
      </div>
      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Fundamental score</CardTitle></CardHeader><CardContent>{summary.score ? <><div className="flex items-center gap-3"><span className="text-4xl font-semibold">{displayValue(summary.score.score)}</span><Badge variant="outline">{summary.score.classification}</Badge></div><p className="mt-3 text-sm text-muted-foreground">{summary.score.explanation}</p><div className="mt-4 flex flex-wrap gap-2">{summary.score.major_contributors.map((item) => <Badge key={item} variant="outline" className="text-xs">{item}</Badge>)}</div></> : <p className="text-sm text-muted-foreground">Score unavailable because required inputs are missing.</p>}</CardContent></Card>
        <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Explainable assessment</CardTitle></CardHeader><CardContent>{summary.analysis ? <><div className="flex items-center gap-2"><Badge variant="outline">{summary.analysis.overall_classification}</Badge><span className="text-xs text-muted-foreground">Rule-based assessment</span></div><ul className="mt-4 space-y-2 text-sm text-muted-foreground">{[...summary.analysis.positive_factors, ...summary.analysis.negative_factors].slice(0, 6).map((item) => <li key={item}>· {item}</li>)}</ul>{summary.analysis.missing_data_warnings.length > 0 && <p className="mt-3 text-xs text-amber-200">Missing: {summary.analysis.missing_data_warnings.join(", ")}</p>}</> : <p className="text-sm text-muted-foreground">Assessment unavailable.</p>}</CardContent></Card>
      </div>
      <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Key ratios</CardTitle></CardHeader><CardContent><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{ratioGroups.flatMap(([, group]) => Object.entries(group as Record<string, { name: string; value: string | number | null; origin: string }>)).map(([key, ratio]) => <div key={key} className="rounded-lg border border-border/60 p-3"><p className="text-xs text-muted-foreground">{ratio.name}</p><p className="mt-1 font-medium">{displayValue(ratio.value)}</p><p className="text-[11px] text-muted-foreground">{ratio.origin}</p></div>)}</div></CardContent></Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Revenue history</CardTitle></CardHeader><CardContent>{history ? <SimpleTrendChart history={history} /> : <p className="text-sm text-muted-foreground">No history available.</p>}</CardContent></Card>
        <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Income statement</CardTitle></CardHeader><CardContent>{statements?.lines.length ? <div className="max-h-48 overflow-auto"><table className="w-full text-left text-xs"><tbody>{statements.lines.slice(0, 12).map((line) => <tr key={`${line.metric_name}-${line.period_end}`} className="border-b border-border/40"><td className="py-2 text-muted-foreground">{line.metric_name}</td><td className="py-2 text-right">{displayValue(line.value)}</td></tr>)}</tbody></table></div> : <p className="text-sm text-muted-foreground">No reported statement lines are available.</p>}</CardContent></Card>
      </div>
      <p className="text-xs text-muted-foreground">Yahoo Finance data can be delayed, stale, revised, or unavailable for some companies and periods. Missing values are intentionally shown as unavailable.</p>
    </section>
  );
}
