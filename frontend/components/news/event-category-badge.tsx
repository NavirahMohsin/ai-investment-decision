'use client';

import {
  TrendingUp,
  Briefcase,
  AlertCircle,
  Scale,
  Users,
  Handshake,
  Zap,
  FileText,
} from 'lucide-react';

interface EventCategoryBadgeProps {
  category: 'earnings' | 'acquisition' | 'litigation' | 'regulatory' | 'management' | 'partnership' | 'product' | 'other';
  compact?: boolean;
}

const categoryConfig = {
  earnings: { color: 'bg-blue-100 text-blue-800', icon: TrendingUp, label: 'Earnings' },
  acquisition: { color: 'bg-purple-100 text-purple-800', icon: Briefcase, label: 'Acquisition' },
  litigation: { color: 'bg-red-100 text-red-800', icon: Scale, label: 'Litigation' },
  regulatory: { color: 'bg-orange-100 text-orange-800', icon: AlertCircle, label: 'Regulatory' },
  management: { color: 'bg-indigo-100 text-indigo-800', icon: Users, label: 'Management' },
  partnership: { color: 'bg-teal-100 text-teal-800', icon: Handshake, label: 'Partnership' },
  product: { color: 'bg-cyan-100 text-cyan-800', icon: Zap, label: 'Product' },
  other: { color: 'bg-gray-100 text-gray-800', icon: FileText, label: 'Other' },
};

export function EventCategoryBadge({ category, compact = false }: EventCategoryBadgeProps) {
  const config = categoryConfig[category];
  const Icon = config.icon;

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg font-medium ${config.color}`}>
      <Icon className="w-4 h-4" />
      <span>{config.label}</span>
    </div>
  );
}
