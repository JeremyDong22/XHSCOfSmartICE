// Account card component for displaying individual account info
// Version: 2.0 - Anthropic-inspired dark theme with muted semantic badges

'use client';

import { useState } from 'react';
import { Account, openBrowser, closeBrowser, deleteAccount } from '@/lib/api';

interface AccountCardProps {
  account: Account;
  onRefresh: () => void;
}

export default function AccountCard({ account, onRefresh }: AccountCardProps) {
  const [loading, setLoading] = useState(false);

  const handleOpenBrowser = async () => {
    setLoading(true);
    try {
      await openBrowser(account.account_id);
      onRefresh();
    } catch (error) {
      console.error('Failed to open browser:', error);
      alert('Failed to open browser');
    } finally {
      setLoading(false);
    }
  };

  const handleCloseBrowser = async () => {
    setLoading(true);
    try {
      await closeBrowser(account.account_id);
      onRefresh();
    } catch (error) {
      console.error('Failed to close browser:', error);
      alert('Failed to close browser');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete Account ${account.account_id}? This cannot be undone.`)) return;

    setLoading(true);
    try {
      await deleteAccount(account.account_id);
      onRefresh();
    } catch (error) {
      console.error('Failed to delete account:', error);
      alert('Failed to delete account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-stone-800 rounded-xl p-5 border border-stone-700 transition-all hover:border-stone-600">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-stone-700 rounded-full flex items-center justify-center">
            <span className="font-mono text-sm text-stone-300">
              {account.account_id}
            </span>
          </div>
          <div>
            <div className="font-medium text-stone-50">
              {account.nickname || `Account ${account.account_id}`}
            </div>
            <div className="font-mono text-xs text-stone-500">
              ID: {account.account_id}
            </div>
          </div>
        </div>

        {/* Status Badge */}
        {account.browser_open ? (
          <span className="font-mono text-xs px-2 py-1 rounded bg-[rgba(16,185,129,0.15)] text-emerald-300 border border-[rgba(16,185,129,0.25)]">
            ACTIVE
          </span>
        ) : (
          <span className="font-mono text-xs px-2 py-1 rounded bg-[rgba(120,113,108,0.15)] text-stone-400 border border-[rgba(120,113,108,0.25)]">
            OFFLINE
          </span>
        )}
      </div>

      {/* Metadata */}
      {account.last_scraped && (
        <div className="font-mono text-xs text-stone-500 mb-4">
          Last scraped: {new Date(account.last_scraped).toLocaleString()}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {account.browser_open ? (
          <button
            onClick={handleCloseBrowser}
            disabled={loading}
            className="flex-1 px-4 py-2 bg-stone-700 text-stone-200 border border-stone-600 rounded-lg text-sm font-medium transition-all hover:bg-stone-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Close Browser
          </button>
        ) : (
          <button
            onClick={handleOpenBrowser}
            disabled={loading}
            className="flex-1 px-4 py-2 bg-[#D97757] text-white rounded-lg text-sm font-medium transition-all hover:bg-[#E8886A] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Open Browser
          </button>
        )}
        <button
          onClick={handleDelete}
          disabled={loading}
          className="px-3 py-2 bg-[rgba(239,68,68,0.2)] text-red-300 border border-[rgba(239,68,68,0.3)] rounded-lg transition-all hover:bg-[rgba(239,68,68,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
          title="Delete account"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
