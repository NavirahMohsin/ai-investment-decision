"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CircleAlert } from "lucide-react";
import { fetchFundamentalsDashboard, type DashboardFundamentals } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function FundamentalsSummary() {
  const [data, setData] = useState<DashboardFundamentals | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    void fetchFundamentalsDashboard().then(setData).catch(() => setError(true));
  }, []);
  if (error) return <Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="flex items-center gap-2 p-5 text-sm text-muted-foreground"><CircleAlert className="size-4" /> Fundamental summary unavailable.</CardContent></Card>;
  if (!data) return <div className="h-36 animate-pulse rounded-xl border border-border/70 bg-card/60" />;
  const profiles = [...data.strong_profiles, ...data.improving_profitability].slice(0, 5);
  return <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Fundamental signals</CardTitle><p className="text-sm text-muted-foreground">Explainable summaries from the latest Yahoo Finance data.</p></CardHeader><CardContent>{profiles.length ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{profiles.map((profile) => <Link key={profile.symbol} href={`/stocks/${profile.symbol}`} className="rounded-lg border border-border/60 p-3 hover:border-cyan-300/50"><p className="font-mono text-xs text-cyan-300">{profile.symbol}</p><p className="mt-1 text-sm font-medium">{profile.name}</p><p className="mt-2 text-xs text-muted-foreground">{"score" in profile && profile.score != null ? `Score ${profile.score}` : "trend" in profile ? profile.trend : "Available"}</p></Link>)}</div> : <p className="text-sm text-muted-foreground">No sufficient fundamental profiles are available yet.</p>}</CardContent></Card>;
}
