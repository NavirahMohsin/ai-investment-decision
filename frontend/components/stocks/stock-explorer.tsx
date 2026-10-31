"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Building2,
  CircleAlert,
  Database,
  FilterX,
  RefreshCw,
  Search,
  Tag,
} from "lucide-react";
import { fetchCompanies, type Company } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

function formatInstrumentType(value: string) {
  return value.replace(/[_-]/g, " ");
}

function StockCard({ company }: { company: Company }) {
  return (
    <Link href={`/stocks/${encodeURIComponent(company.symbol)}`} className="group block">
      <Card className="h-full border-border/70 bg-card/80 shadow-none transition-colors group-hover:border-primary/40 group-hover:bg-card">
        <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
              <Building2 className="size-4" />
            </div>
            <div className="min-w-0">
              <h3 className="truncate font-medium text-foreground">{company.name}</h3>
              <p className="mt-1 font-mono text-xs tracking-wide text-cyan-300">{company.symbol}</p>
            </div>
          </div>
          <Badge variant="outline" className="shrink-0 uppercase text-[10px] tracking-wider">
            {company.exchange}
          </Badge>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border/60 pt-4 text-xs">
          <div>
            <p className="text-muted-foreground">Instrument type</p>
            <p className="mt-1 capitalize text-foreground">{formatInstrumentType(company.instrument_type)}</p>
          </div>
          {company.sector && (
            <div>
              <p className="text-muted-foreground">Sector</p>
              <p className="mt-1 text-foreground">{company.sector}</p>
            </div>
          )}
        </div>
        <div className="mt-4 flex items-center gap-1 text-xs text-cyan-300 opacity-0 transition-opacity group-hover:opacity-100">
          View historical data <ArrowUpRight className="size-3.5" />
        </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function LoadingGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <Card key={index} className="border-border/70 bg-card/70 shadow-none">
          <CardContent className="animate-pulse p-5">
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-xl bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-3/4 rounded bg-muted" />
                <div className="h-3 w-1/3 rounded bg-muted" />
              </div>
            </div>
            <div className="mt-5 border-t border-border/60 pt-4">
              <div className="h-3 w-1/2 rounded bg-muted" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function StockExplorer() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState("");
  const [exchange, setExchange] = useState("");
  const [instrumentType, setInstrumentType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCompanies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCompanies(await fetchCompanies());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load the company catalogue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void fetchCompanies()
      .then((result) => {
        if (active) {
          setCompanies(result);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load the company catalogue.");
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
  }, []);

  const exchanges = useMemo(
    () => [...new Set(companies.map((company) => company.exchange))].sort(),
    [companies],
  );
  const instrumentTypes = useMemo(
    () => [...new Set(companies.map((company) => company.instrument_type))].sort(),
    [companies],
  );
  const filteredCompanies = useMemo(() => {
    const query = search.trim().toLowerCase();
    return companies.filter((company) => {
      const matchesSearch =
        !query ||
        company.name.toLowerCase().includes(query) ||
        company.symbol.toLowerCase().includes(query);
      return (
        matchesSearch &&
        (!exchange || company.exchange === exchange) &&
        (!instrumentType || company.instrument_type === instrumentType)
      );
    });
  }, [companies, exchange, instrumentType, search]);

  const filtersActive = Boolean(search || exchange || instrumentType);
  const clearFilters = () => {
    setSearch("");
    setExchange("");
    setInstrumentType("");
  };

  return (
    <div className="space-y-7">
      <section className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <p className="mb-3 text-sm font-medium text-cyan-300">Indian market universe</p>
          <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">Stock Explorer</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            Browse the available companies and benchmark instruments in the ArthAI research catalogue.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Database className="size-4 text-cyan-300" />
          <span>{loading ? "Loading catalogue..." : `${filteredCompanies.length} of ${companies.length} instruments`}</span>
        </div>
      </section>

      <Card className="border-border/70 bg-card/80 shadow-none">
        <CardContent className="p-4 sm:p-5">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_180px_200px_auto]">
            <label className="relative block">
              <span className="sr-only">Search by company name or symbol</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search company or symbol"
                className="h-10 w-full rounded-lg border border-input bg-background/60 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <label>
              <span className="sr-only">Filter by exchange</span>
              <select
                value={exchange}
                onChange={(event) => setExchange(event.target.value)}
                className="h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              >
                <option value="">All exchanges</option>
                {exchanges.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by instrument type</span>
              <select
                value={instrumentType}
                onChange={(event) => setInstrumentType(event.target.value)}
                className="h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm capitalize text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              >
                <option value="">All instrument types</option>
                {instrumentTypes.map((value) => <option key={value} value={value}>{formatInstrumentType(value)}</option>)}
              </select>
            </label>
            <Button type="button" variant="outline" onClick={clearFilters} disabled={!filtersActive} className="h-10">
              <FilterX className="size-4" />
              Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && <LoadingGrid />}

      {!loading && error && (
        <Card className="border-rose-300/20 bg-rose-300/5 shadow-none">
          <CardContent className="flex flex-col items-center justify-center px-6 py-12 text-center">
            <CircleAlert className="size-7 text-rose-300" />
            <h3 className="mt-4 font-medium text-foreground">Unable to load the catalogue</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">{error}</p>
            <Button type="button" variant="outline" onClick={() => void loadCompanies()} className="mt-5">
              <RefreshCw className="size-4" />
              Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && !error && companies.length === 0 && (
        <Card className="border-border/70 bg-card/80 shadow-none">
          <CardContent className="flex flex-col items-center justify-center px-6 py-14 text-center">
            <Tag className="size-7 text-cyan-300" />
            <h3 className="mt-4 font-medium text-foreground">No instruments available</h3>
            <p className="mt-2 text-sm text-muted-foreground">The company catalogue has not returned any instruments yet.</p>
          </CardContent>
        </Card>
      )}

      {!loading && !error && companies.length > 0 && filteredCompanies.length === 0 && (
        <Card className="border-border/70 bg-card/80 shadow-none">
          <CardContent className="flex flex-col items-center justify-center px-6 py-14 text-center">
            <Search className="size-7 text-cyan-300" />
            <h3 className="mt-4 font-medium text-foreground">No matching instruments</h3>
            <p className="mt-2 text-sm text-muted-foreground">Try a different search or clear the active filters.</p>
            <Button type="button" variant="outline" onClick={clearFilters} className="mt-5">
              <FilterX className="size-4" />
              Clear filters
            </Button>
          </CardContent>
        </Card>
      )}

      {!loading && !error && filteredCompanies.length > 0 && (
        <section aria-label="Company catalogue" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filteredCompanies.map((company) => <StockCard key={company.id} company={company} />)}
        </section>
      )}
    </div>
  );
}
