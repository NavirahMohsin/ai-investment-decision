"use client";

import { useEffect, useState } from "react";
import { CircleAlert, RefreshCw } from "lucide-react";
import { fetchCompanies, fetchCompanyComparison, type Company, type CompanyComparison } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CompanyComparison({ initialSymbols }: { initialSymbols: string[] }) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selected, setSelected] = useState<string[]>(initialSymbols.slice(0, 8));
  const [comparison, setComparison] = useState<CompanyComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchCompanies().then(setCompanies).catch(() => setError("Unable to load the company universe."));
  }, []);

  function toggle(symbol: string) {
    setSelected((current) => current.includes(symbol) ? current.filter((item) => item !== symbol) : current.length < 8 ? [...current, symbol] : current);
  }

  function compare() {
    if (selected.length < 2) {
      setError("Select at least two companies to compare.");
      return;
    }
    setLoading(true);
    setError(null);
    void fetchCompanyComparison(selected)
      .then(setComparison)
      .catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Unable to compare companies."))
      .finally(() => setLoading(false));
  }

  return (
    <section className="space-y-5">
      <Card className="border-border/70 bg-card/80 shadow-none">
        <CardHeader><CardTitle>Select companies</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">{companies.filter((company) => ["company", "equity", "stock"].includes(company.instrument_type.toLowerCase())).map((company) => <Button key={company.symbol} type="button" size="sm" variant={selected.includes(company.symbol) ? "secondary" : "outline"} onClick={() => toggle(company.symbol)}>{company.symbol}</Button>)}</div>
          <div className="mt-4 flex items-center gap-3"><Button onClick={compare} disabled={loading || selected.length < 2}>{loading ? "Comparing..." : "Compare selected"}</Button><span className="text-xs text-muted-foreground">{selected.length}/8 selected</span></div>
        </CardContent>
      </Card>
      {error && <Card className="border-rose-300/20 bg-rose-300/5 shadow-none"><CardContent className="flex items-center gap-3 p-5 text-sm text-rose-200"><CircleAlert className="size-5 shrink-0" />{error}<Button variant="ghost" size="sm" onClick={() => setError(null)}><RefreshCw className="size-4" /></Button></CardContent></Card>}
      {comparison && <Card className="border-border/70 bg-card/80 shadow-none"><CardHeader><CardTitle>Peer comparison</CardTitle><p className="text-sm text-muted-foreground">{comparison.sector_warning ?? "Values are compared using the latest available reported periods."}</p></CardHeader><CardContent className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b border-border/60 text-xs text-muted-foreground"><th className="px-3 py-3">Metric</th>{comparison.companies.map((company) => <th key={company.symbol} className="px-3 py-3">{company.symbol}<span className="block font-normal">{company.name}</span></th>)}</tr></thead><tbody>{comparison.metrics.filter((metric) => metric.comparable || Object.values(metric.values).some((value) => value != null)).slice(0, 18).map((metric) => <tr key={metric.key} className="border-b border-border/40"><td className="px-3 py-3 text-muted-foreground">{metric.label}</td>{comparison.companies.map((company) => <td key={company.symbol} className="px-3 py-3">{company.metrics[metric.key] == null ? "—" : Number(company.metrics[metric.key]).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</td>)}</tr>)}</tbody></table>{comparison.comparability_warnings.length > 0 && <p className="mt-4 text-xs text-amber-200">{comparison.comparability_warnings.join(" ")}</p>}</CardContent></Card>}
    </section>
  );
}
