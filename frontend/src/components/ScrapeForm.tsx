// Scrape form component for starting scraping tasks
// Version: 3.8 - Changed max posts from slider to editable input
// Changes: Replace slider with number input for precise value entry
// Previous: v3.7 - UI localization to Chinese

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
      alert('请选择账号');
      return;
    }
    if (!keyword.trim()) {
      alert('请输入关键词');
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
      alert(error instanceof Error ? error.message : '采集失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-stone-800 rounded-xl p-6 border border-stone-700">
      <h2 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-4">
        启动采集任务
      </h2>

      {accounts.filter(a => a.browser_open).length === 0 ? (
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>暂无打开的浏览器，请先打开浏览器再开始采集。</p>
        </div>
      ) : availableAccounts.length === 0 ? (
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>所有浏览器都在执行任务中。</p>
          <p className="mt-2 text-xs">请等待任务完成或打开新的浏览器。</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Account selector */}
          <div>
            <label htmlFor="account-select" className="block text-sm font-medium text-stone-200 mb-1.5">
              选择账号
            </label>
            <select
              id="account-select"
              value={accountId}
              onChange={(e) => setAccountId(Number(e.target.value))}
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            >
              <option value={0}>-- 选择账号 --</option>
              {availableAccounts.map((acc) => (
                <option key={acc.account_id} value={acc.account_id}>
                  {acc.nickname || `账号 ${acc.account_id}`} (ID: {acc.account_id})
                </option>
              ))}
            </select>
          </div>

          {/* Keyword input */}
          <div>
            <label htmlFor="keyword-input" className="block text-sm font-medium text-stone-200 mb-1.5">
              搜索关键词
            </label>
            <input
              id="keyword-input"
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="例如：咖啡、美食、旅行"
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm placeholder-stone-600 focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            />
          </div>

          {/* Max posts input */}
          <div>
            <label htmlFor="max-posts-input" className="block text-sm font-medium text-stone-200 mb-1.5">
              最大采集数量
            </label>
            <input
              id="max-posts-input"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={maxPosts}
              onChange={(e) => {
                const value = e.target.value.replace(/[^0-9]/g, '');
                const num = parseInt(value, 10) || 1;
                setMaxPosts(Math.min(Math.max(num, 1), 2000));
              }}
              placeholder="1-2000"
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm placeholder-stone-600 focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all font-mono"
            />
            <p className="mt-1.5 text-xs text-stone-500">
              范围: 1 - 2000
            </p>
          </div>

          {/* Min likes filter */}
          <div>
            <label htmlFor="min-likes-input" className="block text-sm font-medium text-stone-200 mb-1.5">
              最低点赞数过滤
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
              placeholder="0 = 不过滤"
              className="w-full px-3.5 py-2.5 bg-stone-900 border border-stone-700 rounded-lg text-stone-50 text-sm placeholder-stone-600 focus:outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.2)] transition-all"
            />
            <p className="mt-1.5 text-xs text-stone-500 font-mono">
              注：搜索模式下不支持收藏数和评论数过滤
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
              跳过视频（仅采集图文）
            </label>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#D97757] text-white font-medium rounded-lg transition-all hover:bg-[#E8886A] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '启动中...' : '开始采集'}
          </button>

          {/* Active tasks info */}
          {activeTasks.size > 0 && (
            <div className="pt-4 border-t border-stone-700">
              <p className="text-xs text-stone-500 font-mono">
                {activeTasks.size} 个任务运行中。查看各账号下方的控制台日志。
              </p>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
