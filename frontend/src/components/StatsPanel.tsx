// Stats panel component displaying dashboard metrics
// Version: 2.3 - UI localization to Chinese
// Changes: All metric labels translated to Chinese
// Previous: Always show stats with current values, no loading state UI change

'use client';

import { Stats } from '@/lib/api';

interface StatsPanelProps {
  stats: Stats | null;
  loading: boolean;
  activeTasksCount?: number;
}

export default function StatsPanel({ stats, loading, activeTasksCount = 0 }: StatsPanelProps) {
  // Always show stats panel without loading skeleton to prevent flash on navigation
  const statItems = [
    {
      value: stats?.total ?? 0,
      label: '账号总数',
      colorClass: 'text-emerald-300',
    },
    {
      value: stats?.browsers_open ?? 0,
      label: '打开的浏览器',
      colorClass: 'text-blue-300',
    },
    {
      value: stats?.with_session ?? 0,
      label: '已登录会话',
      colorClass: 'text-[#D97757]',
    },
    {
      value: activeTasksCount,
      label: '运行中任务',
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
