"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, CalendarDays, CircleAlert, Database, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fetchCompanies, fetchStockHistory, type Company, type HistoricalPriceRecord, type HistoricalPriceResponse } from "@/lib/api";
import { ClosingPriceChart, VolumeChart } from "@/components/stocks/historical-chart";

const ranges = [
  { label: "1M", days: 31 },
  { label: "3M", days: 92 },
  { label: "6M", days: 183 },
  { label: "1Y", days: 365 },
  { label: "5Y", days: 1826 },
] as const;

function formatPrice(value: string | number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
}

function formatDate(value: string | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

function startDateForRange(days: number) {
  const start = new Date();
  start.setUTCDate(start.getUTCDate() - days);
  return start.toISOString().slice(0, 10);
}

function formatInstrumentType(value: string) {
  return value.replace(/[_-]/g, " ");
}

function SummaryValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

export function StockDetail({ symbol }: { symbol: string }) {
  const [company, setCompany] = useState<Company | null>(null);
  const [history, setHistory] = useState<HistoricalPriceResponse | null>(null);
  const [selectedRange, setSelectedRange] = useState("1Y");
  const [loading, setLoading] = useState(true);
  const [companyLoading, setCompanyLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async (rangeLabel: string) => {
    const range = ranges.find((item) => item.label === rangeLabel) ?? ranges[3];
    setLoading(true);
    setError(null);
    try {
      setHistory(await fetchStockHistory(symbol, startDateForRange(range.days), new Date().toISOString().slice(0, 10)));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load historical data.");
      setHistory(null);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    let active = true;
    void fetchCompanies()
      .then((companies) => {
        if (active) {
          setCompany(companies.find((item) => item.symbol.toUpperCase() === symbol.toUpperCase()) ?? null);
        }
      })
      .catch(() => {
        if (active) setCompany(null);
      })
      .finally(() => {
        if (active) setCompanyLoading(false);
      });
    return () => {
      active = false;
    };
  }, [symbol]);

  useEffect(() => {
    let active = true;
    const range = ranges[3];
    void fetchStockHistory(symbol, startDateForRange(range.days), new Date().toISOString().slice(0, 10))
      .then((result) => {
        if (active) {
          setHistory(result);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load historical data.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [symbol]);

  const latest = useMemo<HistoricalPriceRecord | null>(
    () => history?.records.length ? history.records[history.records.length - 1] : null,
    [history],
  );

  return (
    <div className="space-y-7">
      <Link href="/stocks" className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-cyan-300">
        <ArrowLeft className="size-4" /> Back to Stock Explorer
      </Link>
      <section className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-cyan-300">Historical instrument view</p>
            {company && <Badge variant="outline" className="uppercase text-[10px] tracking-wider">{company.exchange}</Badge>}
          </div>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">{company?.name ?? symbol}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="font-mono text-cyan-300">{symbol}</span>
            {company?.sector && <><span className="text-border">·</span><span>{company.sector}</span></>}
            {(company || history) && <><span className="text-border">·</span><span className="capitalize">{formatInstrumentType(company?.instrument_type ?? history?.instrument_type ?? "")}</span></>}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Database className="size-4 text-cyan-300" />
          <span>{history?.source ?? "Historical data source"}</span>
        </div>
      </section>

      {companyLoading && <div className="h-5 w-56 animate-pulse rounded bg-muted" />}

      {error && (
        <Card className="border-rose-300/20 bg-rose-300/5 shadow-none">
          <CardContent className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <CircleAlert className="size-7 text-rose-300" />
            <h3 className="mt-4 font-medium text-foreground">Unable to load historical data</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">{error}</p>
            <Button type="button" variant="outline" onClick={() => void loadHistory(selectedRange)} className="mt-5">
              <RefreshCw className="size-4" /> Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {!error && loading && <div className="h-72 animate-pulse rounded-xl border border-border/70 bg-card/60" />}

      {!error && !loading && history && (
        <>
          <Card className="border-border/70 bg-card/80 shadow-none">
            <CardContent className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div>
                <p className="text-xs text-muted-foreground">Latest available historical close</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight text-foreground">{formatPrice(latest?.close)}</p>
                <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><CalendarDays className="size-3.5" /> {formatDate(latest?.trading_date)}</p>
              </div>
              <div className="flex flex-wrap gap-1 rounded-lg border border-border bg-background/40 p-1" aria-label="Historical data range">
                {ranges.map((range) => (
                  <Button key={range.label} type="button" variant={selectedRange === range.label ? "secondary" : "ghost"} size="sm" onClick={() => { setSelectedRange(range.label); void loadHistory(range.label); }}>
                    {range.label}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
          {history.records.length === 0 ? (
            <Card className="border-border/70 bg-card/80 shadow-none">
              <CardContent className="flex min-h-56 items-center justify-center px-6 text-center text-sm text-muted-foreground">No historical data is available for the selected range.</CardContent>
            </Card>
          ) : (
            <>
              <ClosingPriceChart records={history.records} />
              <VolumeChart records={history.records} />
              <Card className="border-border/70 bg-card/80 shadow-none">
                <CardContent className="grid gap-5 p-5 sm:grid-cols-4 sm:px-6">
                  <SummaryValue label="Open" value={formatPrice(latest?.open)} />
                  <SummaryValue label="High" value={formatPrice(latest?.high)} />
                  <SummaryValue label="Low" value={formatPrice(latest?.low)} />
                  <SummaryValue label="Volume" value={latest ? latest.volume.toLocaleString("en-IN") : "—"} />
                  <p className="text-xs text-muted-foreground sm:col-span-4">Most recent record: {formatDate(latest?.trading_date)}</p>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
