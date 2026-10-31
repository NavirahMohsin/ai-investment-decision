"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, CircleHelp, RefreshCw, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fetchNewsIngestionRuns, fetchNewsSources, type NewsIngestionRun, type NewsSource } from "@/lib/api";

function date(value: string | null) {
  if (!value) return "Not available";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Not available" : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

export function NewsSourceMonitor() {
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    void fetchNewsSources().then(setSources).catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : "Unable to load sources.")).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  const active = sources.filter((source) => source.is_active).length;
  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-4"><div><p className="text-sm text-cyan-300">Configuration boundary</p><h2 className="mt-1 text-xl font-semibold">Source Monitor</h2></div><div className="flex gap-2 text-xs text-muted-foreground"><span>{sources.length} configured</span><span>·</span><span>{active} active</span></div></div>
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm leading-6 text-muted-foreground"><ShieldAlert className="mr-2 inline size-4 text-cyan-300" /> Sources must be approved and activated before ingestion can occur. This view reports database source status only; it does not infer source health or expose registry feed URLs.</div>
      {error ? <Card className="border-destructive/30 bg-destructive/5 shadow-none"><CardContent className="flex items-center justify-between gap-4 p-5"><p className="flex items-center gap-2 text-sm"><AlertCircle className="size-4 text-destructive" />Unable to load sources.</p><Button variant="outline" onClick={load}><RefreshCw className="size-4" /></Button></CardContent></Card> : loading ? <SourceSkeleton /> : sources.length === 0 ? <EmptyMonitor text="No configured news sources are available yet." /> : <div className="grid gap-4 md:grid-cols-2">{sources.map((source) => <Card key={source.id} className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-5"><div className="flex items-start justify-between gap-3"><div><h3 className="font-medium">{source.name}</h3><p className="mt-1 font-mono text-xs text-muted-foreground">{source.provider_key}</p></div><Badge variant={source.is_active ? "default" : "outline"} className="gap-1">{source.is_active ? <CheckCircle2 className="size-3" /> : <CircleHelp className="size-3" />}{source.is_active ? "Active" : "Inactive"}</Badge></div><div className="mt-5 grid grid-cols-2 gap-3 border-t border-border/60 pt-4 text-xs"><div><p className="text-muted-foreground">Type</p><p className="mt-1 uppercase">{source.source_type}</p></div><div><p className="text-muted-foreground">Last successful ingestion</p><p className="mt-1">{date(source.last_success_at)}</p></div></div>{source.last_error && <p className="mt-4 rounded-md bg-destructive/10 p-3 text-xs text-destructive">{source.last_error}</p>}</CardContent></Card>)}</div>}
    </section>
  );
}

function SourceSkeleton() {
  return <div className="grid gap-4 md:grid-cols-2">{[1, 2].map((item) => <Card key={item} className="border-border/70 bg-card/70 shadow-none"><CardContent className="animate-pulse p-5"><div className="h-4 w-2/3 rounded bg-muted" /><div className="mt-3 h-3 w-1/3 rounded bg-muted" /><div className="mt-7 h-12 rounded bg-muted" /></CardContent></Card>)}</div>;
}

function EmptyMonitor({ text }: { text: string }) {
  return <Card className="border-border/70 bg-card/70 shadow-none"><CardContent className="p-8 text-center text-sm text-muted-foreground">{text}</CardContent></Card>;
}

export function NewsIngestionMonitor() {
  const [runs, setRuns] = useState<NewsIngestionRun[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [page, setPage] = useState(1);
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [pagination, setPagination] = useState({ total: 0, page: 1, page_size: 20, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    const controller = new AbortController();
    void Promise.all([fetchNewsIngestionRuns({ page, pageSize: 20, source, status, signal: controller.signal }), fetchNewsSources(controller.signal)])
      .then(([history, sourceList]) => { setRuns(history.items); setPagination(history.pagination); setSources(sourceList); })
      .catch((requestError: unknown) => { if (!(requestError instanceof DOMException && requestError.name === "AbortError")) setError(requestError instanceof Error ? requestError.message : "Unable to load ingestion history."); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [page, source, status]);
  useEffect(() => { const cleanup = load(); return cleanup; }, [load]);
  function filter(setter: (value: string) => void, value: string) { setter(value); setPage(1); }
  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-4"><div><p className="text-sm text-cyan-300">Operational history</p><h2 className="mt-1 text-xl font-semibold">Ingestion Monitor</h2></div><div className="text-xs text-muted-foreground">{pagination.total} total runs</div></div>
      <div className="flex flex-col gap-3 sm:flex-row"><select aria-label="Filter ingestion source" value={source} onChange={(event) => filter(setSource, event.target.value)} className="h-10 rounded-lg border border-input bg-background/60 px-3 text-sm sm:w-64"><option value="">All sources</option>{sources.map((item) => <option key={item.id} value={item.provider_key}>{item.name}</option>)}</select><select aria-label="Filter ingestion status" value={status} onChange={(event) => filter(setStatus, event.target.value)} className="h-10 rounded-lg border border-input bg-background/60 px-3 text-sm sm:w-52"><option value="">All statuses</option><option value="running">Running</option><option value="success">Success</option><option value="partial_success">Partial success</option><option value="failed">Failed</option></select></div>
      <div className="rounded-lg border border-amber-400/20 bg-amber-400/5 p-4 text-sm leading-6 text-muted-foreground"><ShieldAlert className="mr-2 inline size-4 text-amber-300" /> Manual ingestion controls are not exposed because the backend trigger has no authentication or authorization. This monitor is read-only.</div>
      {error ? <Card className="border-destructive/30 bg-destructive/5 shadow-none"><CardContent className="flex items-center justify-between p-5"><p className="flex items-center gap-2 text-sm"><AlertCircle className="size-4 text-destructive" />Unable to load ingestion history.</p><Button variant="outline" onClick={load}><RefreshCw className="size-4" /></Button></CardContent></Card> : loading ? <SourceSkeleton /> : runs.length === 0 ? <EmptyMonitor text="No ingestion history is available yet." /> : <div className="space-y-3">{runs.map((run) => <RunCard key={run.id} run={run} />)}</div>}
      {!loading && !error && pagination.total_pages > 0 && <div className="flex items-center justify-between border-t border-border/60 pt-4 text-xs text-muted-foreground"><span>Page {pagination.page} of {pagination.total_pages}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</Button></div></div>}
    </section>
  );
}

function RunCard({ run }: { run: NewsIngestionRun }) {
  const variant = run.status === "success" ? "default" : run.status === "failed" ? "destructive" : "outline";
  return <Card className="border-border/70 bg-card/80 shadow-none"><CardContent className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-mono text-xs text-muted-foreground">Run #{run.id}</p><h3 className="mt-1 font-medium">{run.source_name || run.source_provider_key || "Source unavailable"}</h3></div><Badge variant={variant}>{run.status.replaceAll("_", " ")}</Badge></div><div className="mt-4 grid grid-cols-2 gap-4 border-t border-border/60 pt-4 text-xs sm:grid-cols-4"><div><p className="text-muted-foreground">Started</p><p className="mt-1">{date(run.started_at)}</p></div><div><p className="text-muted-foreground">Completed</p><p className="mt-1">{date(run.completed_at)}</p></div><div><p className="text-muted-foreground">Discovered / inserted</p><p className="mt-1">{run.articles_discovered} / {run.articles_inserted}</p></div><div><p className="text-muted-foreground">Skipped</p><p className="mt-1">{run.articles_skipped}</p></div></div>{run.error_message && <p className="mt-4 rounded-md bg-destructive/10 p-3 text-xs text-destructive">{run.error_message}</p>}</CardContent></Card>;
}

export function NewsSourcesPage() {
  return <div className="space-y-10"><NewsSourceMonitor /><NewsIngestionMonitor /></div>;
}
