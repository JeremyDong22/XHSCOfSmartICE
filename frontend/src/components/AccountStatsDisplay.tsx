// Account statistics display component with usage alerts
// Version: 1.0 - Shows account usage metrics with color-coded risk indicators
// Purpose: Display scrape counts, browser opens, and duration with anti-crawling alerts

'use client';

import { AccountStats } from '@/lib/api';

interface AccountStatsDisplayProps {
  stats: AccountStats | null;
  loading?: boolean;
}

// Helper: Format seconds to hours:minutes
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours === 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

// Helper: Get alert color for scrapes this hour
function getScrapeHourlyAlertColor(count: number): string {
  if (count > 10) return 'text-red-400 bg-red-900/30';
  if (count > 5) return 'text-yellow-400 bg-yellow-900/30';
  return 'text-green-400 bg-green-900/30';
}

// Helper: Get alert color for browser opens today
function getBrowserOpensAlertColor(count: number): string {
  if (count > 10) return 'text-red-400 bg-red-900/30';
  if (count > 5) return 'text-yellow-400 bg-yellow-900/30';
  return 'text-green-400 bg-green-900/30';
}

// Helper: Get alert color for browser duration today
function getBrowserDurationAlertColor(seconds: number): string {
  const hours = seconds / 3600;
  if (hours > 4) return 'text-red-400 bg-red-900/30';
  if (hours > 2) return 'text-yellow-400 bg-yellow-900/30';
  return 'text-green-400 bg-green-900/30';
}

export default function AccountStatsDisplay({ stats, loading }: AccountStatsDisplayProps) {
  if (loading) {
    return (
      <div className="font-mono text-xs text-stone-500 animate-pulse">
        Loading stats...
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="font-mono text-xs text-stone-500">
        No stats available
      </div>
    );
  }

  const lastUsed = stats.last_used_at
    ? new Date(stats.last_used_at).toLocaleString()
    : 'Unknown';

  return (
    <div className="space-y-2">
      {/* Last Used */}
      <div className="font-mono text-xs text-stone-500">
        Last used: {lastUsed}
      </div>

      {/* Stats Row */}
      <div className="flex flex-wrap gap-2 text-xs font-mono">
        {/* Today Stats */}
        <div className="flex items-center gap-2">
          <span className="text-stone-500">Today:</span>

          {/* Scrapes Today */}
          <span className="text-stone-400">
            {stats.today.scrape_count} scr
          </span>

          {/* Browser Opens Today - with alert */}
          <span
            className={`px-1.5 py-0.5 rounded ${getBrowserOpensAlertColor(stats.today.browser_opens)}`}
            title={`Browser opens today: ${stats.today.browser_opens}\n${
              stats.today.browser_opens > 10 ? 'Warning: High activity!' :
              stats.today.browser_opens > 5 ? 'Caution: Moderate activity' :
              'Safe: Low activity'
            }`}
          >
            {stats.today.browser_opens} opn
          </span>

          {/* Browser Duration Today - with alert */}
          <span
            className={`px-1.5 py-0.5 rounded ${getBrowserDurationAlertColor(stats.today.browser_duration_seconds)}`}
            title={`Browser duration today: ${formatDuration(stats.today.browser_duration_seconds)}\n${
              stats.today.browser_duration_seconds > 14400 ? 'Warning: High usage!' :
              stats.today.browser_duration_seconds > 7200 ? 'Caution: Moderate usage' :
              'Safe: Low usage'
            }`}
          >
            {formatDuration(stats.today.browser_duration_seconds)}
          </span>
        </div>

        {/* Separator */}
        <span className="text-stone-600">|</span>

        {/* This Hour Stats */}
        <div className="flex items-center gap-2">
          <span className="text-stone-500">This hour:</span>

          {/* Scrapes This Hour - with alert */}
          <span
            className={`px-1.5 py-0.5 rounded ${getScrapeHourlyAlertColor(stats.this_hour.scrape_count)}`}
            title={`Scrapes this hour: ${stats.this_hour.scrape_count}\n${
              stats.this_hour.scrape_count > 10 ? 'Warning: High frequency!' :
              stats.this_hour.scrape_count > 5 ? 'Caution: Moderate frequency' :
              'Safe: Low frequency'
            }`}
          >
            {stats.this_hour.scrape_count} scr
          </span>

          {/* Browser Opens This Hour */}
          <span className="text-stone-400">
            {stats.this_hour.browser_opens} opn
          </span>
        </div>
      </div>

      {/* Lifetime Stats (optional, shown in a collapsed way) */}
      <details className="text-xs font-mono text-stone-600">
        <summary className="cursor-pointer hover:text-stone-500">Lifetime stats</summary>
        <div className="mt-2 pl-2 space-y-1">
          <div>Total scrapes: {stats.lifetime.total_scrapes}</div>
          <div>Posts scraped: {stats.lifetime.total_posts_scraped}</div>
          <div>Browser opens: {stats.lifetime.total_browser_opens}</div>
          <div>Total duration: {formatDuration(stats.lifetime.total_browser_duration_seconds)}</div>
        </div>
      </details>
    </div>
  );
}
