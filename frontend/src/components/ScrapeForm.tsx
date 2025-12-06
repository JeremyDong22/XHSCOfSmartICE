// Scrape form component for starting scraping tasks
// Version: 3.5 - Increased max posts limit to 2000
// Changes: Max posts slider now allows up to 2000 posts per account per session
// Previous: Step changed from 5 to 1 for smooth sliding, min changed to 1

'use client';

import { useState } from 'react';
import { Account, startScrapeAsync } from '@/lib/api';
import { ActiveTask } from './AccountCardWithConsole';

interface ScrapeFormProps {
  accounts: Account[];
  activeTasks: Map<number, ActiveTask>;
  onTaskStart: (accountId: number, task: ActiveTask) => void;
}

export default function ScrapeForm({ accounts, activeTasks, onTaskStart }: ScrapeFormProps) {
  const [loading, setLoading] = useState(false);

  const [accountId, setAccountId] = useState<number>(0);
  const [keyword, setKeyword] = useState('');
  const [maxPosts, setMaxPosts] = useState(20);
  const [minLikesInput, setMinLikesInput] = useState('');
  const [skipVideos, setSkipVideos] = useState(true); // Default: skip videos, only get images

  // Available accounts: browser open and not currently running a task
  const availableAccounts = accounts.filter(a =>
    a.browser_open && !activeTasks.has(a.account_id)
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!accountId) {
      alert('Please select an account');
      return;
    }
    if (!keyword.trim()) {
      alert('Please enter a keyword');
      return;
    }

    setLoading(true);

    // Parse minLikes from string input (empty = 0)
    const minLikes = minLikesInput.trim() === '' ? 0 : parseInt(minLikesInput, 10) || 0;

    try {
      const response = await startScrapeAsync({
        account_id: accountId,
        keyword: keyword.trim(),
        max_posts: maxPosts,
        min_likes: minLikes,
        min_collects: 0,
        min_comments: 0,
        skip_videos: skipVideos,
      });

      // Dispatch task to the account
      onTaskStart(accountId, {
        taskId: response.task_id,
        keyword: keyword.trim(),
        startedAt: new Date(),
      });

      // Reset form for next task
      setAccountId(0);
      setKeyword('');
      setMinLikesInput('');
    } catch (error) {
      console.error('Scrape failed:', error);
      alert(error instanceof Error ? error.message : 'Scrape failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-stone-800 rounded-xl p-6 border border-stone-700">
      <h2 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-4">
        Start Scraping Task
      </h2>

      {accounts.filter(a => a.browser_open).length === 0 ? (
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>No browsers open. Open a browser first to start scraping.</p>
        </div>
      ) : availableAccounts.length === 0 ? (
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>All open browsers are currently running tasks.</p>
          <p className="mt-2 text-xs">Wait for a task to complete or open another browser.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Account selector */}
          <div>
            <label htmlFor="account-select" className="block text-sm font-medium text-stone-200 mb-1.5">
              Select Account
            </label>
            <select
              id="account-select"
              value={accountId}
              onChange={(e) => setAccountId(Number(e.target.value))}
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            >
              <option value={0}>-- Select Account --</option>
              {availableAccounts.map((acc) => (
                <option key={acc.account_id} value={acc.account_id}>
                  Account {acc.account_id} {acc.nickname ? `(${acc.nickname})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Keyword input */}
          <div>
            <label htmlFor="keyword-input" className="block text-sm font-medium text-stone-200 mb-1.5">
              Search Keyword
            </label>
            <input
              id="keyword-input"
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g., 咖啡, 美食, 旅行"
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm placeholder-stone-600 focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            />
          </div>

          {/* Max posts slider */}
          <div>
            <label htmlFor="max-posts-slider" className="block text-sm font-medium text-stone-200 mb-1.5">
              Max Posts: <span className="font-mono text-[#D97757]">{maxPosts}</span>
            </label>
            <input
              id="max-posts-slider"
              type="range"
              min={1}
              max={2000}
              step={1}
              value={maxPosts}
              onChange={(e) => setMaxPosts(Number(e.target.value))}
              aria-valuemin={1}
              aria-valuemax={2000}
              aria-valuenow={maxPosts}
              className="w-full cursor-pointer"
            />
          </div>

          {/* Min likes filter */}
          <div>
            <label htmlFor="min-likes-input" className="block text-sm font-medium text-stone-200 mb-1.5">
              Min Likes Filter
            </label>
            <input
              id="min-likes-input"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={minLikesInput}
              onChange={(e) => {
                // Only allow digits
                const value = e.target.value.replace(/[^0-9]/g, '');
                setMinLikesInput(value);
              }}
              placeholder="0 = no filter"
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm placeholder-stone-600 focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            />
            <p className="mt-1.5 text-xs text-stone-500 font-mono">
              Note: Collects and comments filters not available in search-only mode
            </p>
          </div>

          {/* Skip videos checkbox */}
          <div className="flex items-center gap-3">
            <input
              id="skip-videos-checkbox"
              type="checkbox"
              checked={skipVideos}
              onChange={(e) => setSkipVideos(e.target.checked)}
              className="w-4 h-4 rounded border-stone-700 bg-stone-900 text-[#D97757] focus:ring-[#D97757] focus:ring-offset-stone-900"
            />
            <label htmlFor="skip-videos-checkbox" className="text-sm font-medium text-stone-200 cursor-pointer">
              Skip videos (images only)
            </label>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#D97757] text-white font-medium rounded-lg transition-all hover:bg-[#E8886A] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Starting...' : 'Start Scraping'}
          </button>

          {/* Active tasks info */}
          {activeTasks.size > 0 && (
            <div className="pt-4 border-t border-stone-700">
              <p className="text-xs text-stone-500 font-mono">
                {activeTasks.size} task{activeTasks.size > 1 ? 's' : ''} running. See console logs below each account.
              </p>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
