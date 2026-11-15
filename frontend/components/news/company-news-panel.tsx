'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { NewsArticleCard } from './news-article-card';
import { SentimentBadge } from './sentiment-badge';
import { Loader2, Filter, RefreshCw } from 'lucide-react';
import { API_URL } from '@/lib/api';

interface CompanyNewsPanelProps {
  companyId: number;
  companySymbol?: string;
  maxItems?: number;
  showFilters?: boolean;
}

interface NewsArticle {
  id: number;
  headline: string;
  sentiment: {
    score: number;
    confidence: number;
    label: string;
  };
  event: {
    category: string;
    confidence: number;
  };
  market_impact_score: number;
  published_at?: string;
}

interface SentimentPeriod {
  avg_sentiment: number;
  sentiment_trend: string;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  article_count: number;
}

export function CompanyNewsPanel({
  companyId,
  companySymbol = 'STOCK',
  maxItems = 10,
  showFilters = true,
}: CompanyNewsPanelProps) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [sentiment, setSentiment] = useState<SentimentPeriod | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedSentiment, setSelectedSentiment] = useState<string | null>(null);

  const handleRefreshNews = async () => {
    setRefreshing(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/news/refresh`, {
        method: 'POST',
        cache: 'no-store'
      });
      if (res.ok) {
        // Refetch articles after refresh
        const data = await res.json();
        console.log('News refreshed:', data);
        // Trigger data fetch again
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to refresh news:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch current sentiment
        const sentimentRes = await fetch(
          `${API_URL}/api/v1/news/company/${companyId}/sentiment?days=30`,
          { cache: 'no-store' }
        );
        if (sentimentRes.ok) {
          setSentiment(await sentimentRes.json());
        }

        // Build article query
        let articleUrl = `${API_URL}/api/v1/news/company/${companyId}/articles?limit=${maxItems}`;
        if (selectedCategory) articleUrl += `&category=${selectedCategory}`;
        if (selectedSentiment) articleUrl += `&sentiment=${selectedSentiment}`;

        const articlesRes = await fetch(articleUrl, { cache: 'no-store' });
        if (articlesRes.ok) {
          setArticles(await articlesRes.json());
        }
      } catch (err) {
        console.error('Failed to fetch news data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [companyId, selectedCategory, selectedSentiment, maxItems]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent News</CardTitle>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Recent News for {companySymbol}</CardTitle>
            <CardDescription>Last 30 days of news and events</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handleRefreshNews}
              disabled={refreshing}
              className="gap-1"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            {sentiment && (
              <SentimentBadge
                sentiment={sentiment.sentiment_trend as any}
                score={sentiment.avg_sentiment}
              />
            )}
          </div>
        </div>

        {/* Sentiment Stats */}
        {sentiment && (
          <div className="mt-4 grid grid-cols-4 gap-2 text-sm">
            <div className="bg-gray-50 p-2 rounded">
              <div className="text-muted-foreground">Total</div>
              <div className="font-semibold">{sentiment.article_count}</div>
            </div>
            <div className="bg-green-50 p-2 rounded">
              <div className="text-green-700 text-xs">Positive</div>
              <div className="font-semibold text-green-700">{sentiment.positive_count}</div>
            </div>
            <div className="bg-red-50 p-2 rounded">
              <div className="text-red-700 text-xs">Negative</div>
              <div className="font-semibold text-red-700">{sentiment.negative_count}</div>
            </div>
            <div className="bg-gray-50 p-2 rounded">
              <div className="text-muted-foreground text-xs">Neutral</div>
              <div className="font-semibold">{sentiment.neutral_count}</div>
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Filters */}
        {showFilters && (
          <div className="flex flex-wrap gap-2 pb-4 border-b">
            <Button
              variant={selectedCategory === null ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(null)}
            >
              All Events
            </Button>
            {['earnings', 'acquisition', 'litigation', 'regulatory'].map((cat) => (
              <Button
                key={cat}
                variant={selectedCategory === cat ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedCategory(cat)}
              >
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </Button>
            ))}
          </div>
        )}

        {/* Articles */}
        {articles.length > 0 ? (
          <div className="space-y-3">
            {articles.map((article) => (
              <NewsArticleCard
                key={article.id}
                id={article.id}
                headline={article.headline}
                publishedAt={article.published_at}
                sentiment={{
                  score: article.sentiment.score,
                  confidence: article.sentiment.confidence,
                  label: article.sentiment.label as any,
                }}
                event={{
                  category: article.event.category,
                  confidence: article.event.confidence,
                }}
                marketImpactScore={article.market_impact_score}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No articles found for the selected filters
          </div>
        )}
      </CardContent>
    </Card>
  );
}
