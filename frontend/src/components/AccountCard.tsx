// Account card component for displaying individual account info
// Version: 1.0 - Shows account status, session, browser controls

'use client';

import { Account, openBrowser, closeBrowser, deleteAccount } from '@/lib/api';
import { useState } from 'react';

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
    if (!confirm(`Are you sure you want to delete Account ${account.account_id}? This will also delete browser session data.`)) {
      return;
    }
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
    <div className={`bg-white rounded-xl p-5 shadow-sm border-2 transition-all ${
      account.browser_open ? 'border-green-400' : 'border-transparent'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold text-lg ${
            account.active ? 'bg-gradient-to-br from-pink-500 to-rose-500' : 'bg-gray-400'
          }`}>
            {account.account_id}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">
              {account.nickname || `Account ${account.account_id}`}
            </h3>
            <div className="flex gap-2 mt-1">
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                account.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
              }`}>
                {account.active ? 'Active' : 'Inactive'}
              </span>
              {account.has_session && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                  Session
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Browser status indicator */}
        {account.browser_open && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            <span className="text-xs text-green-600 font-medium">Browser Open</span>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="text-sm text-gray-500 mb-4 space-y-1">
        <p>Created: {new Date(account.created_at).toLocaleDateString()}</p>
        {account.last_used && (
          <p>Last used: {new Date(account.last_used).toLocaleDateString()}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {account.browser_open ? (
          <button
            onClick={handleCloseBrowser}
            disabled={loading}
            className="flex-1 px-3 py-2 bg-orange-100 text-orange-700 rounded-lg text-sm font-medium hover:bg-orange-200 transition-colors disabled:opacity-50"
          >
            {loading ? 'Closing...' : 'Close Browser'}
          </button>
        ) : (
          <button
            onClick={handleOpenBrowser}
            disabled={loading || !account.active}
            className="flex-1 px-3 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 transition-colors disabled:opacity-50"
          >
            {loading ? 'Opening...' : 'Open Browser'}
          </button>
        )}
        <button
          onClick={handleDelete}
          disabled={loading}
          className="px-3 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200 transition-colors disabled:opacity-50"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
