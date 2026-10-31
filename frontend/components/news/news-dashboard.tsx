"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  FilterX,
  Newspaper,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  fetchCompanies,
  fetchNews,
  fetchNewsSources,
  type Company,
  type NewsArticle,
  type NewsSource,
} from "@/lib/api";

const PAGE_SIZE = 20;

function formatDate(value: string | null) {
  if (!value) return "Publication date unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Publication date unavailable";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function formatConfidence(value: string | number | null) {
  if (value === null) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${Math.round(numeric * 100)}% match` : null;
}

function NewsCard({ article }: { article: NewsArticle }) {
  return (
    <Card className="border-border/70 bg-card/80 shadow-none transition-colors hover:border-primary/35">
      <CardContent className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
          <span className="font-medium text-cyan-300">{article.source_name}</span>
          <span className="text-border">•</span>
          <span>{formatDate(article.published_at)}</span>
          {article.language && <Badge variant="outline" className="text-[10px] uppercase">{article.language}</Badge>}
        </div>
        <div className="mt-3 flex items-start justify-between gap-4">
          <a href={article.canonical_url} target="_blank" rel="noopener noreferrer" className="text-lg font-semibold leading-7 text-foreground transition-colors hover:text-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {article.headline}
          </a>
          <a
            href={article.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open original article: ${article.headline}`}
            className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowUpRight className="size-4" />
          </a>
        </div>
        {article.companies.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2 border-t border-border/60 pt-4">
            {article.companies.map((company) => (
              <Badge key={`${article.id}-${company.company_id}`} variant="secondary" className="gap-1.5 font-normal">
                <span className="font-mono text-cyan-300">{company.symbol}</span>
                <span>{company.name}</span>
                {formatConfidence(company.match_confidence) && (
                  <span className="text-muted-foreground">· {formatConfidence(company.match_confidence)}</span>
                )}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LoadingCards() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }, (_, index) => (
        <Card key={index} className="border-border/70 bg-card/70 shadow-none">
          <CardContent className="animate-pulse p-6">
            <div className="h-3 w-1/3 rounded bg-muted" />
            <div className="mt-4 h-6 w-4/5 rounded bg-muted" />
            <div className="mt-4 space-y-2">
              <div className="h-3 w-full rounded bg-muted" />
              <div className="h-3 w-2/3 rounded bg-muted" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function NewsDashboard() {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [company, setCompany] = useState("");
  const [source, setSource] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: PAGE_SIZE, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [dateError, setDateError] = useState<string | null>(null);
  const requestId = useRef(0);
  const newsController = useRef<AbortController | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    newsController.current?.abort();
    const controller = new AbortController();
    newsController.current = controller;
    void Promise.all([
      fetchCompanies(),
      fetchNewsSources(controller.signal),
    ]).then(([companyResult, sourceResult]) => {
      setCompanies(companyResult.filter((item) => item.is_active));
      setSources(sourceResult);
      setSourcesError(null);
    }).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setSourcesError(requestError instanceof Error ? requestError.message : "Unable to load filter options.");
    }).finally(() => setSourcesLoading(false));
    return () => controller.abort();
  }, []);

  const loadNews = useCallback(async () => {
    const currentRequest = ++requestId.current;
    if (startDate && endDate && startDate > endDate) {
      setDateError("Publication start date cannot be after the end date.");
      setArticles([]);
      setLoading(false);
      setRefreshing(false);
      return;
    }
    setDateError(null);
    setError(null);
    setLoading(true);
    setRefreshing(true);
    const controller = new AbortController();
    try {
      const result = await fetchNews({
        page,
        pageSize: PAGE_SIZE,
        company,
        source,
        startDate,
        endDate,
        search: debouncedSearch,
        signal: controller.signal,
      });
      if (currentRequest === requestId.current) {
        setArticles(result.items);
        setPagination(result.pagination);
      }
    } catch (requestError: unknown) {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      if (currentRequest === requestId.current) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load financial news.");
        setArticles([]);
      }
    } finally {
      if (currentRequest === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
    return () => controller.abort();
  }, [company, debouncedSearch, endDate, page, source, startDate]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadNews(), 0);
    return () => window.clearTimeout(timer);
  }, [loadNews]);

  useEffect(() => () => newsController.current?.abort(), []);

  const filtersActive = Boolean(search || company || source || startDate || endDate);
  const selectedSource = useMemo(() => sources.find((item) => item.provider_key === source), [source, sources]);

  function clearFilters() {
    setSearch("");
    setDebouncedSearch("");
    setCompany("");
    setSource("");
    setStartDate("");
    setEndDate("");
    setPage(1);
  }

  function changeFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  return (
    <div className="space-y-7">
      <section className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-cyan-300">
            <Newspaper className="size-4" />
            Financial research workspace
          </div>
          <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">Financial News Intelligence</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            Track financial developments, market announcements, and company-related news.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CircleDot className="size-3.5 text-cyan-300" />
          Stored news data · no live streaming
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {([
          ["Matching articles", loading ? "—" : pagination.total.toLocaleString("en-IN"), Newspaper],
          ["Configured sources", sourcesLoading ? "—" : sources.length.toLocaleString("en-IN"), SlidersHorizontal],
          ["Displayed now", loading ? "—" : articles.length.toLocaleString("en-IN"), CheckCircle2],
          ["Page", loading ? "—" : `${pagination.page} / ${Math.max(pagination.total_pages, 1)}`, CalendarDays],
        ] as [string, string, ComponentType<{ className?: string }>][]).map(([label, value, Icon]) => (
          <Card key={String(label)} className="border-border/70 bg-card/70 shadow-none">
            <CardContent className="flex items-center gap-3 p-4">
              <div className="flex size-9 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
                <Icon className="size-4" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card className="border-border/70 bg-card/80 shadow-none">
        <CardContent className="p-4 sm:p-5">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1.4fr)_1fr_1fr_1fr_1fr_auto]">
            <label className="relative block">
              <span className="sr-only">Search news headlines</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input value={search} onChange={(event) => changeFilter(setSearch, event.target.value)} placeholder="Search headlines" type="search" className="h-10 w-full rounded-lg border border-input bg-background/60 pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20" />
            </label>
            <label>
              <span className="sr-only">Filter by company</span>
              <select value={company} onChange={(event) => changeFilter(setCompany, event.target.value)} className="h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20">
                <option value="">All companies</option>
                {companies.map((item) => <option key={item.id} value={item.symbol}>{item.symbol} · {item.name}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by source</span>
              <select value={source} onChange={(event) => changeFilter(setSource, event.target.value)} className="h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20">
                <option value="">All sources</option>
                {sources.map((item) => <option key={item.id} value={item.provider_key}>{item.name}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Publication start date</span>
              <input aria-label="Publication start date" value={startDate} onChange={(event) => changeFilter(setStartDate, event.target.value)} type="date" className="h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
            </label>
            <label>
              <span className="sr-only">Publication end date</span>
              <input aria-label="Publication end date" value={endDate} onChange={(event) => changeFilter(setEndDate, event.target.value)} type="date" className="h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
            </label>
            <Button type="button" variant="outline" onClick={clearFilters} disabled={!filtersActive} className="h-10 gap-2">
              <FilterX className="size-4" /> Clear
            </Button>
          </div>
          {dateError && <p className="mt-3 flex items-center gap-2 text-xs text-destructive"><AlertCircle className="size-3.5" />{dateError}</p>}
          {sourcesError && <p className="mt-3 text-xs text-amber-300">Source filters unavailable: {sourcesError}</p>}
          {selectedSource && <p className="mt-3 text-xs text-muted-foreground">Showing source: <span className="text-foreground">{selectedSource.name}</span></p>}
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/30 bg-destructive/5 shadow-none">
          <CardContent className="flex flex-col items-center justify-center p-10 text-center">
            <AlertCircle className="size-6 text-destructive" />
            <h3 className="mt-4 font-medium">Unable to load financial news</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">{error}</p>
            <Button className="mt-5 gap-2" onClick={() => void loadNews()}><RefreshCw className="size-4" /> Retry</Button>
          </CardContent>
        </Card>
      ) : loading ? (
        <LoadingCards />
      ) : articles.length === 0 ? (
        <Card className="border-border/70 bg-card/70 shadow-none">
          <CardContent className="flex min-h-[300px] flex-col items-center justify-center p-8 text-center">
            <div className="flex size-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary"><Newspaper className="size-6" /></div>
            <h3 className="mt-5 text-lg font-semibold">{filtersActive ? "No matching news articles" : "No news articles are available yet."}</h3>
            <p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
              {filtersActive ? "Try adjusting or clearing your filters." : "News will appear here once approved sources are configured and the ingestion pipeline has collected articles."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <section className="space-y-4" aria-label="Financial news feed">
          {refreshing && <p className="text-xs text-muted-foreground">Refreshing stored news…</p>}
          {articles.map((article) => <NewsCard key={article.id} article={article} />)}
        </section>
      )}

      {!loading && !error && pagination.total_pages > 0 && (
        <div className="flex flex-col items-center justify-between gap-3 border-t border-border/60 pt-5 sm:flex-row">
          <p className="text-xs text-muted-foreground">Page {pagination.page} of {pagination.total_pages} · {pagination.total.toLocaleString("en-IN")} matching articles</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft className="size-4" /> Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next <ChevronRight className="size-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
}
