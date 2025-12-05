// Stats panel component for dashboard overview
// Version: 1.0 - Displays account and browser statistics

import { Stats } from '@/lib/api';

interface StatsPanelProps {
  stats: Stats | null;
  loading: boolean;
}

export default function StatsPanel({ stats, loading }: StatsPanelProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white rounded-xl p-6 shadow-sm animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-20 mb-2"></div>
            <div className="h-8 bg-gray-200 rounded w-12"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const statItems = [
    { label: 'Total Accounts', value: stats.total, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Active Accounts', value: stats.active, color: 'text-green-600', bg: 'bg-green-50' },
    { label: 'With Session', value: stats.with_session, color: 'text-purple-600', bg: 'bg-purple-50' },
    { label: 'Browsers Open', value: stats.browsers_open, color: 'text-orange-600', bg: 'bg-orange-50' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      {statItems.map((item) => (
        <div key={item.label} className={`${item.bg} rounded-xl p-6 shadow-sm`}>
          <p className="text-gray-600 text-sm font-medium">{item.label}</p>
          <p className={`text-3xl font-bold ${item.color} mt-1`}>{item.value}</p>
        </div>
      ))}
    </div>
  );
}
