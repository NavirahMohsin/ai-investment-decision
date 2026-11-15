'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SentimentBadge } from './sentiment-badge';
import { EventCategoryBadge } from './event-category-badge';
import { TrendingUp, ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface NewsArticleCardProps {
  id: number;
  headline: string;
  publishedAt?: string;
  sentiment: {
    score: number;
    confidence: number;
    label: 'positive' | 'negative' | 'neutral';
  };
  event: {
    category: string;
    confidence: number;
  };
  marketImpactScore: number;
  companies?: string[];
  onClick?: () => void;
}

export function NewsArticleCard({
  id,
  headline,
  publishedAt,
  sentiment,
  event,
  marketImpactScore,
  companies = [],
  onClick,
}: NewsArticleCardProps) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getImpactIcon = (score: number) => {
    if (score > 0.7) return <ArrowUpRight className="w-4 h-4 text-red-500" />;
    return <TrendingUp className="w-4 h-4 text-yellow-500" />;
  };

  return (
    <Card
      className={`cursor-pointer transition-all hover:shadow-md ${
        sentiment.label === 'positive'
          ? 'border-green-200'
          : sentiment.label === 'negative'
            ? 'border-red-200'
            : ''
      }`}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <CardTitle className="text-base line-clamp-2">{headline}</CardTitle>
            <CardDescription className="mt-1">{formatDate(publishedAt)}</CardDescription>
          </div>
          {getImpactIcon(marketImpactScore)}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Sentiment and Event Badges */}
        <div className="flex flex-wrap gap-2">
          <SentimentBadge sentiment={sentiment.label} score={sentiment.score} compact />
          <EventCategoryBadge
            category={event.category as any}
            compact
          />
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <div className="text-muted-foreground">Sentiment</div>
            <div className="font-semibold">{(sentiment.confidence * 100).toFixed(0)}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">Category</div>
            <div className="font-semibold">{(event.confidence * 100).toFixed(0)}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">Impact</div>
            <div className="font-semibold">{(marketImpactScore * 100).toFixed(0)}%</div>
          </div>
        </div>

        {/* Companies */}
        {companies.length > 0 && (
          <div className="pt-2 border-t">
            <div className="text-xs text-muted-foreground mb-1">Companies</div>
            <div className="flex flex-wrap gap-1">
              {companies.map((company) => (
                <span
                  key={company}
                  className="inline-block px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                >
                  {company}
                </span>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
