// XHS Multi-Account Scraper Dashboard - Redesigned for parallel scraping
// Version: 3.0 - New layout: ScrapeForm at top, Accounts with console logs, Results at bottom
// Framework: Next.js 16 + React 19 + Tailwind CSS

'use client';

import { useState, useEffect, useCallback } from 'react';
import { Account, Stats, getAccounts, getStats, openBrowserForLogin, closeAllBrowsers, openAllBrowsers } from '@/lib/api';
import StatsPanel from '@/components/StatsPanel';
import AccountCardWithConsole, { ActiveTask } from '@/components/AccountCardWithConsole';
import ScrapeForm from '@/components/ScrapeForm';
import ResultsViewer from '@/components/ResultsViewer';

export default function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [resultsRefresh, setResultsRefresh] = useState(0);

  // Track active scrape tasks per account
  const [activeTasks, setActiveTasks] = useState<Map<number, ActiveTask>>(new Map());

  const loadData = useCallback(async () => {
    try {
      const [accountsData, statsData] = await Promise.all([
        getAccounts(),
        getStats(),
      ]);
      setAccounts(prev => JSON.stringify(prev) === JSON.stringify(accountsData) ? prev : accountsData);
      setStats(prev => JSON.stringify(prev) === JSON.stringify(statsData) ? prev : statsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleAddAccount = async () => {
    setActionLoading(true);
    try {
      const accountId = await openBrowserForLogin();
      alert(`New account ${accountId} created! Please login in the browser window.`);
      loadData();
    } catch (error) {
      console.error('Failed to add account:', error);
      alert('Failed to create new account');
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenAll = async () => {
    setActionLoading(true);
    try {
      await openAllBrowsers();
      loadData();
    } catch (error) {
      console.error('Failed to open all browsers:', error);
      alert('Failed to open all browsers');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseAll = async () => {
    setActionLoading(true);
    try {
      await closeAllBrowsers();
      loadData();
    } catch (error) {
      console.error('Failed to close all browsers:', error);
      alert('Failed to close all browsers');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle new task started
  const handleTaskStart = (accountId: number, task: ActiveTask) => {
    setActiveTasks(prev => {
      const next = new Map(prev);
      next.set(accountId, task);
      return next;
    });
  };

  // Handle task completion
  const handleTaskComplete = (accountId: number, status: string) => {
    console.log(`Task for account ${accountId} ${status}`);
    setActiveTasks(prev => {
      const next = new Map(prev);
      next.delete(accountId);
      return next;
    });
    // Refresh results when task completes
    if (status === 'completed') {
      setResultsRefresh(prev => prev + 1);
    }
    loadData();
  };

  return (
    <div className="min-h-screen bg-stone-900">
      {/* Header */}
      <header className="bg-stone-800 border-b border-stone-700 py-6 px-8">
        <div className="max-w-[1400px] mx-auto">
          <h1 className="text-2xl font-semibold text-stone-50 tracking-tight">
            XHS Multi-Account Scraper
          </h1>
          <p className="text-sm text-stone-500 mt-1 font-mono">
            Manage accounts and scrape Xiaohongshu posts in parallel
          </p>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-8 py-8">
        {/* Stats Panel */}
        <StatsPanel stats={stats} loading={loading} activeTasksCount={activeTasks.size} />

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3 mb-8">
          <button
            onClick={handleAddAccount}
            disabled={actionLoading}
            className="px-5 py-2.5 bg-[rgba(16,185,129,0.2)] text-emerald-300 border border-[rgba(16,185,129,0.3)] rounded-lg font-medium text-sm transition-all hover:bg-[rgba(16,185,129,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            + Add New Account
          </button>
          <button
            onClick={handleOpenAll}
            disabled={actionLoading}
            className="px-5 py-2.5 bg-[rgba(59,130,246,0.2)] text-blue-300 border border-[rgba(59,130,246,0.3)] rounded-lg font-medium text-sm transition-all hover:bg-[rgba(59,130,246,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Open All Browsers
          </button>
          <button
            onClick={handleCloseAll}
            disabled={actionLoading}
            className="px-5 py-2.5 bg-[rgba(245,158,11,0.2)] text-amber-300 border border-[rgba(245,158,11,0.3)] rounded-lg font-medium text-sm transition-all hover:bg-[rgba(245,158,11,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Close All Browsers
          </button>

          {/* Active tasks indicator */}
          {activeTasks.size > 0 && (
            <div className="ml-auto flex items-center gap-2 px-4 py-2 bg-[rgba(217,119,87,0.15)] border border-[rgba(217,119,87,0.25)] rounded-lg">
              <div className="w-2 h-2 bg-[#D97757] rounded-full animate-pulse"></div>
              <span className="text-sm text-[#E8A090] font-mono">
                {activeTasks.size} task{activeTasks.size > 1 ? 's' : ''} running
              </span>
            </div>
          )}
        </div>

        {/* Accounts Section with Console Logs */}
        <div className="mb-8">
          <h2 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-4">
            Accounts
          </h2>
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-stone-800 rounded-xl p-5 border border-stone-700 animate-pulse">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-stone-700 rounded-full"></div>
                    <div className="flex-1">
                      <div className="h-4 bg-stone-700 rounded w-24 mb-2"></div>
                      <div className="h-3 bg-stone-700 rounded w-16"></div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <div className="h-9 bg-stone-700 rounded flex-1"></div>
                    <div className="h-9 bg-stone-700 rounded w-16"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : accounts.length === 0 ? (
            <div className="bg-stone-800 rounded-xl p-8 text-center text-stone-500 border border-stone-700">
              <p>No accounts yet. Click &quot;Add New Account&quot; to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {accounts.map((account) => (
                <AccountCardWithConsole
                  key={account.account_id}
                  account={account}
                  activeTask={activeTasks.get(account.account_id) || null}
                  onRefresh={loadData}
                  onTaskComplete={handleTaskComplete}
                />
              ))}
            </div>
          )}
        </div>

        {/* Start Scraping Task Form */}
        <div className="mb-8">
          <ScrapeForm
            accounts={accounts}
            activeTasks={activeTasks}
            onTaskStart={handleTaskStart}
          />
        </div>

        {/* Scraping Results Section */}
        <div>
          <ResultsViewer refreshTrigger={resultsRefresh} />
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-16 py-6 text-center text-stone-600 text-sm font-mono">
        <p>XHS Multi-Account Scraper</p>
      </footer>
    </div>
  );
}
