"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Building2, CircleAlert, ExternalLink, Newspaper, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchCompanyNews, fetchNewsArticle, type NewsArticle, type NewsArticleDetail } from "@/lib/api";

function formatDate(value: string | null) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function confidence(value: string | number | null) {
  if (value === null) return null;
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number * 100)}% rule score` : null;
}

function RelatedNews({ article, symbol }: { article: NewsArticleDetail; symbol: string }) {
  const [related, setRelated] = useState<NewsArticle[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetchCompanyNews(symbol, { page: 1, pageSize: 5, signal: controller.signal })
      .then((response) => setRelated(response.items.filter((item) => item.id !== article.id).slice(0, 4)))
      .catch((requestError: unknown) => {
        if (!(requestError instanceof DOMException && requestError.name === "AbortError")) setError(true);
      });
    return () => controller.abort();
  }, [article.id, symbol]);
  if (error || related.length === 0) return null;
  return (
    <Card className="border-border/70 bg-card/80 shadow-none">
      <CardHeader><CardTitle>Related {symbol} coverage</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {related.map((item) => (
          <Link key={item.id} href={`/news/${item.id}`} className="block rounded-lg border border-border/60 p-3 transition-colors hover:border-primary/40 hover:bg-muted/40">
            <p className="text-sm font-medium leading-5">{item.headline}</p>
            <p className="mt-1 text-xs text-muted-foreground">{formatDate(item.published_at)} · {item.source_name}</p>
          </Link>
        ))}
        <Link href={`/news?company=${encodeURIComponent(symbol)}`} className="inline-flex items-center gap-1 text-xs font-medium text-cyan-300 hover:text-cyan-200">
          View more company news <ArrowUpRight className="size-3.5" />
        </Link>
      </CardContent>
    </Card>
  );
}

export function NewsDetail() {
  const params = useParams<{ articleId: string }>();
  const articleId = Number(params.articleId);
  const [article, setArticle] = useState<NewsArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!Number.isInteger(articleId) || articleId <= 0) return;
    const controller = new AbortController();
    void fetchNewsArticle(articleId, controller.signal)
      .then(setArticle)
      .catch((requestError: unknown) => {
        if (!(requestError instanceof DOMException && requestError.name === "AbortError")) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load this article.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [articleId]);

  if (!Number.isInteger(articleId) || articleId <= 0) return <p className="text-sm text-destructive">Invalid article ID.</p>;
  if (loading) return <div className="space-y-4">{[1, 2, 3].map((item) => <Card key={item} className="border-border/70 bg-card/70 shadow-none"><CardContent className="animate-pulse p-6"><div className="h-4 w-1/3 rounded bg-muted" /><div className="mt-5 h-8 w-5/6 rounded bg-muted" /><div className="mt-5 h-24 rounded bg-muted" /></CardContent></Card>)}</div>;
  if (error || !article) return <Card className="border-destructive/30 bg-destructive/5 shadow-none"><CardContent className="flex flex-col items-center p-10 text-center"><CircleAlert className="size-6 text-destructive" /><h2 className="mt-4 font-medium">Unable to load article</h2><p className="mt-2 text-sm text-muted-foreground">{error || "This article is unavailable."}</p><Button className="mt-5 gap-2" onClick={() => window.location.reload()}><RefreshCw className="size-4" /> Retry</Button></CardContent></Card>;
  const primaryCompany = article.companies[0];
  return (
    <div className="space-y-6">
      <Link href="/news" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-cyan-300"><ArrowLeft className="size-4" /> Back to News</Link>
      <Card className="border-border/70 bg-card/80 shadow-none">
        <CardContent className="p-6 sm:p-8">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-cyan-300">{article.source_name}</span>
            <span>·</span><span>{formatDate(article.published_at)}</span>
            {article.language && <Badge variant="outline" className="uppercase">{article.language}</Badge>}
          </div>
          <h1 className="mt-5 max-w-4xl text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{article.headline}</h1>
          <p className="mt-5 max-w-3xl text-sm leading-6 text-muted-foreground">This metadata is provided for research discovery. The full article is hosted by the original publisher.</p>
          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border/60 pt-5 text-sm">
            {article.author && <span className="text-muted-foreground">By <span className="text-foreground">{article.author}</span></span>}
            <a href={article.canonical_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-cyan-300 hover:text-cyan-200"><ExternalLink className="size-4" /> Open original article</a>
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)]">
        <Card className="border-border/70 bg-card/80 shadow-none">
          <CardHeader><CardTitle className="flex items-center gap-2"><Building2 className="size-4 text-cyan-300" /> Associated companies</CardTitle></CardHeader>
          <CardContent>
            {article.companies.length === 0 ? <p className="text-sm text-muted-foreground">No companies are associated with this article.</p> : <div className="space-y-3">{article.companies.map((company) => <div key={company.company_id} className="rounded-lg border border-border/60 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><span className="font-mono text-cyan-300">{company.symbol}</span><span className="ml-3 font-medium">{company.name}</span></div><Badge variant="secondary">{company.match_method}</Badge></div><div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">{confidence(company.match_confidence) && <span>{confidence(company.match_confidence)}</span>}{company.matched_text && <span>Matched text: “{company.matched_text}”</span>}</div></div>)}</div>}
          </CardContent>
        </Card>
        <Card className="border-border/70 bg-card/70 shadow-none">
          <CardHeader><CardTitle className="flex items-center gap-2"><Newspaper className="size-4 text-cyan-300" /> Research metadata</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">{[["Article ID", article.id], ["Publisher", article.source_name], ["Published", formatDate(article.published_at)], ["Language", article.language || "Unavailable"], ["Company links", article.companies.length]].map(([label, value]) => <div key={String(label)} className="flex justify-between gap-4 border-b border-border/50 pb-2 last:border-0"><span className="text-muted-foreground">{label}</span><span className="text-right">{value}</span></div>)}</CardContent>
        </Card>
      </div>
      {primaryCompany && <RelatedNews article={article} symbol={primaryCompany.symbol} />}
    </div>
  );
}
