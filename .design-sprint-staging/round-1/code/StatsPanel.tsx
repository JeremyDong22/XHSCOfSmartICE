// Stats panel component displaying dashboard metrics
// Version: 2.0 - Anthropic-inspired dark theme with monospace numbers

'use client';

import { Stats } from '@/lib/api';

interface StatsPanelProps {
  stats: Stats | null;
  loading: boolean;
}

export default function StatsPanel({ stats, loading }: StatsPanelProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-stone-900 border border-stone-700 rounded-xl p-4 animate-pulse">
            <div className="h-7 bg-stone-700 rounded w-16 mb-2"></div>
            <div className="h-4 bg-stone-700 rounded w-24"></div>
          </div>
        ))}
      </div>
    );
  }

  const statItems = [
    {
      value: stats?.total_accounts ?? 0,
      label: 'Total Accounts',
      colorClass: 'text-emerald-300',
    },
    {
      value: stats?.open_browsers ?? 0,
      label: 'Open Browsers',
      colorClass: 'text-blue-300',
    },
    {
      value: stats?.total_scraped ?? 0,
      label: 'Posts Scraped',
      colorClass: 'text-[#D97757]',
    },
    {
      value: stats?.active_tasks ?? 0,
      label: 'Active Tasks',
      colorClass: 'text-amber-300',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {statItems.map((item, index) => (
        <div
          key={index}
          className="bg-stone-900 border border-stone-700 rounded-xl p-4"
        >
          <div className={`font-mono text-2xl font-semibold ${item.colorClass}`}>
            {item.value.toLocaleString()}
          </div>
          <div className="text-xs text-stone-500 mt-1">
            {item.label}
          </div>
        </div>
      ))}
    </div>
  );
}