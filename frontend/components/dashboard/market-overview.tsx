"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, TrendingDown, TrendingUp, Activity } from "lucide-react";
import { fetchMarketOverview, type MarketOverviewResponse } from "@/lib/api";
import { MarketStatCard } from "@/components/dashboard/market-stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface MarketMover {
  symbol: string;
  name: string;
  close: number;
  change_pct: number;
  volume: number;
  trading_date: string;
}

interface MarketMoversResponse {
  gainers: MarketMover[];
  losers: MarketMover[];
  most_active: MarketMover[];
}

export function MarketOverview() {
  const [overview, setOverview] = useState<MarketOverviewResponse | null>(null);
  const [movers, setMovers] = useState<MarketMoversResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    void fetchMarketOverview()
      .then((result) => {
        if (active) setOverview(result);
      })
      .catch(() => {
        if (active) setError(true);
      });
    
    // Fetch market movers
    void fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/market/movers?limit=5`)
      .then((res) => res.json())
      .then((data: MarketMoversResponse) => {
        if (active) setMovers(data);
      })
      .catch(() => {
        // Silently fail for movers
      });
    
    return () => {
      active = false;
    };
  }, []);

  const index = (symbol: string) => overview?.instruments.find((item) => item.symbol === symbol);
  const formatValue = (value: string | number | null | undefined) =>
    value === null || value === undefined ? "--" : Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  const formatChange = (value: string | number | null | undefined) =>
    value === null || value === undefined ? "No historical data" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;

  return (
    <section aria-labelledby="market-overview-title" className="space-y-6">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-cyan-300">Live context</p>
          <h2 id="market-overview-title" className="mt-1 text-lg font-semibold">Market overview</h2>
        </div>
        <span className="text-xs text-muted-foreground">
          {error ? "Data unavailable" : overview ? `Session: ${overview.market_status}` : "Loading market data..."}
        </span>
      </div>
      
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MarketStatCard label="NIFTY 50" type="index" value={formatValue(index("NIFTY50")?.latest_close)} detail={formatChange(index("NIFTY50")?.percentage_change)} />
        <MarketStatCard label="SENSEX" type="index" value={formatValue(index("SENSEX")?.latest_close)} detail={formatChange(index("SENSEX")?.percentage_change)} />
        <MarketStatCard label="Market session" type="sentiment" value={overview?.market_status ?? "--"} detail="Asia/Kolkata" />
        <MarketStatCard label="Tracked instruments" type="companies" value={overview ? String(overview.instruments.length) : "--"} detail="Yahoo Finance history" />
      </div>

      {movers && (movers.gainers.length > 0 || movers.losers.length > 0) && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="border-border/70 bg-card/80 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <TrendingUp className="size-4 text-emerald-400" />
                Top gainers
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {movers.gainers.length === 0 && (
                <p className="text-xs text-muted-foreground">No gainers available</p>
              )}
              {movers.gainers.slice(0, 5).map((mover) => (
                <Link
                  key={mover.symbol}
                  href={`/stocks/${mover.symbol}`}
                  className="flex items-center justify-between rounded-lg border border-border/60 bg-background/40 p-2 transition-colors hover:border-primary/40 hover:bg-background/60"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-xs font-medium">{mover.symbol}</p>
                    <p className="truncate text-xs text-muted-foreground">{formatValue(mover.close)}</p>
                  </div>
                  <Badge variant="outline" className="shrink-0 border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                    +{mover.change_pct.toFixed(2)}%
                  </Badge>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/80 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <TrendingDown className="size-4 text-rose-400" />
                Top losers
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {movers.losers.length === 0 && (
                <p className="text-xs text-muted-foreground">No losers available</p>
              )}
              {movers.losers.slice(0, 5).map((mover) => (
                <Link
                  key={mover.symbol}
                  href={`/stocks/${mover.symbol}`}
                  className="flex items-center justify-between rounded-lg border border-border/60 bg-background/40 p-2 transition-colors hover:border-primary/40 hover:bg-background/60"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-xs font-medium">{mover.symbol}</p>
                    <p className="truncate text-xs text-muted-foreground">{formatValue(mover.close)}</p>
                  </div>
                  <Badge variant="outline" className="shrink-0 border-rose-500/30 bg-rose-500/10 text-rose-400">
                    {mover.change_pct.toFixed(2)}%
                  </Badge>
                </Link>
              ))}
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/80 shadow-none">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <Activity className="size-4 text-cyan-300" />
                Most active
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {movers.most_active.length === 0 && (
                <p className="text-xs text-muted-foreground">No data available</p>
              )}
              {movers.most_active.slice(0, 5).map((mover) => (
                <Link
                  key={mover.symbol}
                  href={`/stocks/${mover.symbol}`}
                  className="flex items-center justify-between rounded-lg border border-border/60 bg-background/40 p-2 transition-colors hover:border-primary/40 hover:bg-background/60"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-mono text-xs font-medium">{mover.symbol}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      Vol: {(mover.volume / 1000000).toFixed(2)}M
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className={`shrink-0 ${
                      mover.change_pct >= 0
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                        : "border-rose-500/30 bg-rose-500/10 text-rose-400"
                    }`}
                  >
                    {mover.change_pct >= 0 ? "+" : ""}{mover.change_pct.toFixed(2)}%
                  </Badge>
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  );
}
