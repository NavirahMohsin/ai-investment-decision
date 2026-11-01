"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, CircleAlert } from "lucide-react";
import { fetchSectorIntelligence, fetchSectors, type SectorIntelligence, type SectorListItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SectorIntelligence() {
  const [sectors, setSectors] = useState<SectorListItem[]>([]);
  const [selected, setSelected] = useState("");
  const [data, setData] = useState<SectorIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchSectors()
      .then((items) => {
        setSectors(items);
        if (items[0]) setSelected(items[0].sector);
      })
      .catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Unable to load sectors."));
  }, []);

  useEffect(() => {
    if (!selected) return;
    void fetchSectorIntelligence(selected)
      .then(setData)
      .catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Unable to load sector intelligence."));
  }, [selected]);

  if (error && !data) return <Card className="border-rose-300/20 bg-rose-300/5 shadow-none"><CardContent className="flex items-center gap-2 p-6 text-sm text-rose-200"><CircleAlert className="size-5" />{error}</CardContent></Card>;
  return (
    <div className="space-y-5">
      <Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="flex flex-wrap gap-2 p-4">{sectors.map((item) => <button key={item.sector} type="button" onClick={() => setSelected(item.sector)} className={`rounded-lg border px-3 py-2 text-sm transition-colors ${selected === item.sector ? "border-cyan-300/60 bg-cyan-300/10 text-cyan-200" : "border-border/60 text-muted-foreground hover:text-foreground"}`}>{item.sector}<span className="ml-2 text-xs">{item.company_count}</span></button>)}</CardContent></Card>
      {!data && <div className="h-96 animate-pulse rounded-xl border border-border/70 bg-card/60" />}
      {data && <><div className="grid gap-4 sm:grid-cols-3"><Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-5"><p className="text-xs text-muted-foreground">Tracked companies</p><p className="mt-2 text-2xl font-semibold">{data.tracked_company_count}</p></CardContent></Card><Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-5"><p className="text-xs text-muted-foreground">Average daily change</p><p className="mt-2 text-2xl font-semibold">{data.average_daily_change_pct == null ? "—" : `${Number(data.average_daily_change_pct).toFixed(2)}%`}</p></CardContent></Card><Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-5"><p className="text-xs text-muted-foreground">Average fundamental score</p><p className="mt-2 text-2xl font-semibold">{data.average_fundamental_score == null ? "—" : Number(data.average_fundamental_score).toFixed(1)}</p></CardContent></Card></div><Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="size-4 text-cyan-300" /> Sector rankings</CardTitle><p className="text-sm text-muted-foreground">Ranked within the tracked ArthAI universe; missing values remain unavailable.</p></CardHeader><CardContent className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead><tr className="border-b border-border/60 text-xs text-muted-foreground"><th className="px-3 py-3">Company</th><th className="px-3 py-3">Industry</th><th className="px-3 py-3">Price</th><th className="px-3 py-3">Daily change</th><th className="px-3 py-3">Fundamental score</th><th className="px-3 py-3">Assessment</th></tr></thead><tbody>{data.companies.map((company) => <tr key={company.symbol} className="border-b border-border/40"><td className="px-3 py-3"><Link href={`/stocks/${company.symbol}`} className="text-cyan-300 hover:underline">{company.symbol}</Link><span className="ml-2 text-xs text-muted-foreground">{company.name}</span></td><td className="px-3 py-3 text-muted-foreground">{company.industry ?? "—"}</td><td className="px-3 py-3">{company.latest_close == null ? "—" : Number(company.latest_close).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td><td className="px-3 py-3">{company.daily_change_pct == null ? "—" : `${Number(company.daily_change_pct).toFixed(2)}%`}</td><td className="px-3 py-3">{company.fundamental_score == null ? "—" : Number(company.fundamental_score).toFixed(1)}</td><td className="px-3 py-3"><Badge variant="outline">{company.classification ?? "Unavailable"}</Badge></td></tr>)}</tbody></table><div className="mt-4 space-y-1 text-xs text-amber-200">{data.warnings.map((warning) => <p key={warning}>• {warning}</p>)}</div></CardContent></Card></>}
    </div>
  );
}
