'use client';

import { ArrowUp, ArrowDown, TrendingUp } from 'lucide-react';

interface SentimentBadgeProps {
  sentiment: 'positive' | 'negative' | 'neutral';
  score?: number;
  compact?: boolean;
}

export function SentimentBadge({ sentiment, score, compact = false }: SentimentBadgeProps) {
  const bgColor =
    sentiment === 'positive'
      ? 'bg-green-100 text-green-800'
      : sentiment === 'negative'
        ? 'bg-red-100 text-red-800'
        : 'bg-gray-100 text-gray-800';

  const icon =
    sentiment === 'positive' ? (
      <ArrowUp className="w-3 h-3" />
    ) : sentiment === 'negative' ? (
      <ArrowDown className="w-3 h-3" />
    ) : (
      <TrendingUp className="w-3 h-3" />
    );

  const label = sentiment.charAt(0).toUpperCase() + sentiment.slice(1);
  const scoreStr = score !== undefined ? ` ${score > 0 ? '+' : ''}${(score * 100).toFixed(0)}%` : '';

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${bgColor}`}>
        {icon}
        {label}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg font-medium ${bgColor}`}>
      {icon}
      <span>{label}</span>
      {scoreStr && <span className="text-sm opacity-75">{scoreStr}</span>}
    </div>
  );
}
