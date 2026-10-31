import { MarketStatCard } from "@/components/dashboard/market-stat-card";

export function MarketOverview() {
  return (
    <section aria-labelledby="market-overview-title">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-cyan-300">Live context</p>
          <h2 id="market-overview-title" className="mt-1 text-lg font-semibold">Market overview</h2>
        </div>
        <span className="text-xs text-muted-foreground">Data status: pending integration</span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MarketStatCard label="NIFTY 50" type="index" />
        <MarketStatCard label="SENSEX" type="index" />
        <MarketStatCard label="Market Sentiment" type="sentiment" />
        <MarketStatCard label="Tracked Companies" type="companies" />
      </div>
    </section>
  );
}
