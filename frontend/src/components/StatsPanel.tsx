// Stats panel component displaying dashboard metrics
// Version: 2.1 - Fixed to match actual Stats interface from API

'use client';

import { Stats } from '@/lib/api';

interface StatsPanelProps {
  stats: Stats | null;
  loading: boolean;
  activeTasksCount?: number;
}

export default function StatsPanel({ stats, loading, activeTasksCount = 0 }: StatsPanelProps) {
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
      value: stats?.total ?? 0,
      label: 'Total Accounts',
      colorClass: 'text-emerald-300',
    },
    {
      value: stats?.browsers_open ?? 0,
      label: 'Open Browsers',
      colorClass: 'text-blue-300',
    },
    {
      value: stats?.with_session ?? 0,
      label: 'With Session',
      colorClass: 'text-[#D97757]',
    },
    {
      value: activeTasksCount,
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
