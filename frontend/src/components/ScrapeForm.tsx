// Scrape form component for starting scraping tasks
// Version: 1.0 - Form with keyword, filters, and account selection

'use client';

import { useState } from 'react';
import { Account, startScrape } from '@/lib/api';

interface ScrapeFormProps {
  accounts: Account[];
  onComplete: () => void;
}

export default function ScrapeForm({ accounts, onComplete }: ScrapeFormProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ posts: number; file: string } | null>(null);

  // Form state
  const [accountId, setAccountId] = useState<number>(0);
  const [keyword, setKeyword] = useState('');
  const [maxPosts, setMaxPosts] = useState(20);
  const [minLikes, setMinLikes] = useState(0);
  const [minCollects, setMinCollects] = useState(0);
  const [minComments, setMinComments] = useState(0);

  // Filter accounts with open browsers
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

    try {
      const response = await startScrape({
        account_id: accountId,
        keyword: keyword.trim(),
        max_posts: maxPosts,
        min_likes: minLikes,
        min_collects: minCollects,
        min_comments: minComments,
      });

      setResult({
        posts: response.posts_count,
        file: response.filepath,
      });
      onComplete();
    } catch (error) {
      console.error('Scrape failed:', error);
      alert(error instanceof Error ? error.message : 'Scrape failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Start Scraping Task</h2>

      {availableAccounts.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No browsers open. Open a browser first to start scraping.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Account selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select Account
            </label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
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
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search Keyword
            </label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g., 咖啡, 美食, 旅行"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
            />
          </div>

          {/* Max posts slider */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Posts: {maxPosts}
            </label>
            <input
              type="range"
              min={5}
              max={100}
              step={5}
              value={maxPosts}
              onChange={(e) => setMaxPosts(Number(e.target.value))}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-pink-500"
            />
          </div>

          {/* Filters */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Likes
              </label>
              <input
                type="number"
                min={0}
                value={minLikes}
                onChange={(e) => setMinLikes(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Collects
              </label>
              <input
                type="number"
                min={0}
                value={minCollects}
                onChange={(e) => setMinCollects(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Comments
              </label>
              <input
                type="number"
                min={0}
                value={minComments}
                onChange={(e) => setMinComments(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-pink-500 to-rose-500 text-white font-semibold rounded-lg hover:from-pink-600 hover:to-rose-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Scraping...' : 'Start Scraping'}
          </button>

          {/* Result */}
          {result && (
            <div className="mt-4 p-4 bg-green-50 rounded-lg">
              <p className="text-green-700 font-medium">
                Scraping complete! Found {result.posts} posts.
              </p>
              <p className="text-sm text-green-600 mt-1">
                Saved to: {result.file}
              </p>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
