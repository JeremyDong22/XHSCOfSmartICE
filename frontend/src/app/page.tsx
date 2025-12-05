// XHS Multi-Account Scraper Dashboard
// Version: 1.0 - Main dashboard page with account management and scraping

'use client';

import { useState, useEffect, useCallback } from 'react';
import { Account, Stats, getAccounts, getStats, openBrowserForLogin, closeAllBrowsers, openAllBrowsers } from '@/lib/api';
import StatsPanel from '@/components/StatsPanel';
import AccountCard from '@/components/AccountCard';
import ScrapeForm from '@/components/ScrapeForm';
import ResultsViewer from '@/components/ResultsViewer';

export default function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [resultsRefresh, setResultsRefresh] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const [accountsData, statsData] = await Promise.all([
        getAccounts(),
        getStats(),
      ]);
      setAccounts(accountsData);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Auto-refresh every 5 seconds
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

  const handleScrapeComplete = () => {
    setResultsRefresh((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-pink-500 to-rose-500 text-white py-6 px-8 shadow-lg">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold">XHS Multi-Account Scraper</h1>
          <p className="text-pink-100 mt-1">Manage accounts and scrape Xiaohongshu posts</p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-8">
        {/* Stats Panel */}
        <StatsPanel stats={stats} loading={loading} />

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3 mb-8">
          <button
            onClick={handleAddAccount}
            disabled={actionLoading}
            className="px-4 py-2 bg-green-500 text-white rounded-lg font-medium hover:bg-green-600 transition-colors disabled:opacity-50"
          >
            + Add New Account
          </button>
          <button
            onClick={handleOpenAll}
            disabled={actionLoading}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 transition-colors disabled:opacity-50"
          >
            Open All Browsers
          </button>
          <button
            onClick={handleCloseAll}
            disabled={actionLoading}
            className="px-4 py-2 bg-orange-500 text-white rounded-lg font-medium hover:bg-orange-600 transition-colors disabled:opacity-50"
          >
            Close All Browsers
          </button>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Accounts Section */}
          <div className="lg:col-span-2">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Accounts</h2>
            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="bg-white rounded-xl p-5 shadow-sm animate-pulse">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
                      <div className="flex-1">
                        <div className="h-4 bg-gray-200 rounded w-24 mb-2"></div>
                        <div className="h-3 bg-gray-200 rounded w-16"></div>
                      </div>
                    </div>
                    <div className="h-3 bg-gray-200 rounded w-full mb-4"></div>
                    <div className="flex gap-2">
                      <div className="h-9 bg-gray-200 rounded flex-1"></div>
                      <div className="h-9 bg-gray-200 rounded w-16"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : accounts.length === 0 ? (
              <div className="bg-white rounded-xl p-8 text-center text-gray-500">
                <p>No accounts yet. Click &quot;Add New Account&quot; to get started.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {accounts.map((account) => (
                  <AccountCard
                    key={account.account_id}
                    account={account}
                    onRefresh={loadData}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-8">
            {/* Scrape Form */}
            <ScrapeForm accounts={accounts} onComplete={handleScrapeComplete} />

            {/* Results Viewer */}
            <ResultsViewer refreshTrigger={resultsRefresh} />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-16 py-6 text-center text-gray-500 text-sm">
        <p>XHS Multi-Account Scraper &copy; 2024</p>
      </footer>
    </div>
  );
}
