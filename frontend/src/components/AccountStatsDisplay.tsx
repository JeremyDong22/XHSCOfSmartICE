// Account statistics display component with usage alerts
// Version: 1.2 - Updated alert thresholds for scrapes, posts, and browser opens per hour
// Changes: Scrapes (10/20), Posts (200/300), Opens (5/10) for yellow/red thresholds
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
  if (count > 20) return 'text-red-400 bg-red-900/30';
  if (count > 10) return 'text-yellow-400 bg-yellow-900/30';
  return 'text-green-400 bg-green-900/30';
}

// Helper: Get alert color for posts scraped this hour
function getPostsHourlyAlertColor(count: number): string {
  if (count > 300) return 'text-red-400 bg-red-900/30';
  if (count > 200) return 'text-yellow-400 bg-yellow-900/30';
  return 'text-green-400 bg-green-900/30';
}

// Helper: Get alert color for browser opens this hour
function getBrowserOpensHourlyAlertColor(count: number): string {
  if (count > 10) return 'text-red-400 bg-red-900/30';
  if (count > 5) return 'text-yellow-400 bg-yellow-900/30';
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

      {/* Main View - This Hour Stats Only */}
      <div className="flex flex-wrap gap-2 text-xs font-mono">
        <span className="text-stone-500">This hour:</span>

        {/* Scrapes This Hour - with alert */}
        <span
          className={`px-1.5 py-0.5 rounded ${getScrapeHourlyAlertColor(stats.this_hour.scrape_count)}`}
          title={`Scrapes this hour: ${stats.this_hour.scrape_count}\n${
            stats.this_hour.scrape_count > 20 ? 'Warning: High frequency (>20/hr)!' :
            stats.this_hour.scrape_count > 10 ? 'Caution: Moderate frequency (>10/hr)' :
            'Safe: Low frequency (≤10/hr)'
          }`}
        >
          {stats.this_hour.scrape_count} scrapes
        </span>

        <span className="text-stone-600">|</span>

        {/* Posts Scraped This Hour - with alert */}
        <span
          className={`px-1.5 py-0.5 rounded ${getPostsHourlyAlertColor(stats.this_hour.posts_scraped)}`}
          title={`Posts scraped this hour: ${stats.this_hour.posts_scraped}\n${
            stats.this_hour.posts_scraped > 300 ? 'Warning: High volume (>300/hr)!' :
            stats.this_hour.posts_scraped > 200 ? 'Caution: Moderate volume (>200/hr)' :
            'Safe: Low volume (≤200/hr)'
          }`}
        >
          {stats.this_hour.posts_scraped} posts
        </span>

        <span className="text-stone-600">|</span>

        {/* Browser Opens This Hour - with alert */}
        <span
          className={`px-1.5 py-0.5 rounded ${getBrowserOpensHourlyAlertColor(stats.this_hour.browser_opens)}`}
          title={`Browser opens this hour: ${stats.this_hour.browser_opens}\n${
            stats.this_hour.browser_opens > 10 ? 'Warning: High activity (>10/hr)!' :
            stats.this_hour.browser_opens > 5 ? 'Caution: Moderate activity (>5/hr)' :
            'Safe: Low activity (≤5/hr)'
          }`}
        >
          {stats.this_hour.browser_opens} opens
        </span>
      </div>

      {/* Dropdown - Today + Lifetime Stats Side-by-Side */}
      <details className="text-xs font-mono text-stone-600">
        <summary className="cursor-pointer hover:text-stone-500">More stats</summary>
        <div className="mt-2 grid grid-cols-2 gap-4 pl-2">
          {/* Today Column */}
          <div className="space-y-1">
            <div className="font-semibold text-stone-400 mb-1.5">Today</div>
            <div>Scrapes: <span className="font-mono">{stats.today.scrape_count}</span></div>
            <div>Posts: <span className="font-mono">{stats.today.posts_scraped}</span></div>
            <div>Opens: <span className="font-mono">{stats.today.browser_opens}</span></div>
            <div>Duration: <span className="font-mono">{formatDuration(stats.today.browser_duration_seconds)}</span></div>
          </div>

          {/* Lifetime Column */}
          <div className="space-y-1">
            <div className="font-semibold text-stone-400 mb-1.5">Lifetime</div>
            <div>Scrapes: <span className="font-mono">{stats.lifetime.total_scrapes}</span></div>
            <div>Posts: <span className="font-mono">{stats.lifetime.total_posts_scraped}</span></div>
            <div>Opens: <span className="font-mono">{stats.lifetime.total_browser_opens}</span></div>
            <div>Duration: <span className="font-mono">{formatDuration(stats.lifetime.total_browser_duration_seconds)}</span></div>
          </div>
        </div>
      </details>
    </div>
  );
}
