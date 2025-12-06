// Scrape form component for starting scraping tasks
// Version: 2.0 - Anthropic-inspired dark theme with terracotta primary button

'use client';

import { useState } from 'react';
import { Account, startScrapeAsync, cancelScrape } from '@/lib/api';
import LogConsole from './LogConsole';

interface ScrapeFormProps {
  accounts: Account[];
  onComplete: () => void;
}

export default function ScrapeForm({ accounts, onComplete }: ScrapeFormProps) {
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const [accountId, setAccountId] = useState<number>(0);
  const [keyword, setKeyword] = useState('');
  const [maxPosts, setMaxPosts] = useState(20);
  const [minLikes, setMinLikes] = useState(0);

  const availableAccounts = accounts.filter(a => a.browser_open);

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
    setResult(null);
    setTaskId(null);

    try {
      const response = await startScrapeAsync({
        account_id: accountId,
        keyword: keyword.trim(),
        max_posts: maxPosts,
        min_likes: minLikes,
        min_collects: 0,
        min_comments: 0,
      });

      setTaskId(response.task_id);
    } catch (error) {
      console.error('Scrape failed:', error);
      alert(error instanceof Error ? error.message : 'Scrape failed');
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!taskId) return;

    try {
      await cancelScrape(taskId);
    } catch (error) {
      console.error('Cancel failed:', error);
      alert(error instanceof Error ? error.message : 'Failed to cancel');
    }
  };

  const handleLogComplete = (status: string) => {
    setLoading(false);
    setResult(status === 'completed' ? 'Scrape completed successfully!' : `Scrape ${status}`);
    onComplete();
  };

  return (
    <div className="bg-stone-800 rounded-xl p-6 border border-stone-700">
      <h2 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-4">
        Start Scraping Task
      </h2>

      {availableAccounts.length === 0 ? (
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>No browsers open. Open a browser first to start scraping.</p>
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
              min={5}
              max={100}
              step={5}
              value={maxPosts}
              onChange={(e) => setMaxPosts(Number(e.target.value))}
              aria-valuemin={5}
              aria-valuemax={100}
              aria-valuenow={maxPosts}
              className="w-full h-2 bg-stone-700 rounded-lg appearance-none cursor-pointer accent-[#D97757]"
            />
          </div>

          {/* Min likes filter */}
          <div>
            <label htmlFor="min-likes-input" className="block text-sm font-medium text-stone-200 mb-1.5">
              Min Likes Filter
            </label>
            <input
              id="min-likes-input"
              type="number"
              min={0}
              value={minLikes}
              onChange={(e) => setMinLikes(Number(e.target.value))}
              placeholder="0 = no filter"
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm placeholder-stone-600 focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            />
            <p className="mt-1.5 text-xs text-stone-500 font-mono">
              Note: Collects and comments filters not available in search-only mode
            </p>
          </div>

          {/* Submit/Stop buttons */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-3 bg-[#D97757] text-white font-medium rounded-lg transition-all hover:bg-[#E8886A] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Scraping...' : 'Start Scraping'}
            </button>
            {loading && (
              <button
                type="button"
                onClick={handleStop}
                className="px-6 py-3 bg-[rgba(239,68,68,0.2)] text-red-300 border border-[rgba(239,68,68,0.3)] font-medium rounded-lg transition-all hover:bg-[rgba(239,68,68,0.3)]"
              >
                Stop
              </button>
            )}
          </div>

          {/* Log console */}
          {taskId && (
            <div className="mt-4">
              <LogConsole taskId={taskId} onComplete={handleLogComplete} />
            </div>
          )}

          {/* Result */}
          {result && !loading && (
            <div className="mt-4 p-4 bg-[rgba(16,185,129,0.15)] border border-[rgba(16,185,129,0.25)] rounded-lg">
              <p className="text-emerald-300 font-medium text-sm">{result}</p>
            </div>
          )}
        </form>
      )}
    </div>
  );
}