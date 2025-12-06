// Account card component with embedded console log for active scrape tasks
// Version: 1.1 - Added account stats display with usage alerts
// Changes: Integrated AccountStatsDisplay component with auto-refresh every 30s
// Previous: Shows account info with console log underneath when task is running

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Account, AccountStats, openBrowser, closeBrowser, deleteAccount, cancelScrape, getAccountStats } from '@/lib/api';
import AccountStatsDisplay from './AccountStatsDisplay';

// Task info passed from parent
export interface ActiveTask {
  taskId: string;
  keyword: string;
  startedAt: Date;
}

interface AccountCardWithConsoleProps {
  account: Account;
  activeTask: ActiveTask | null;
  onRefresh: () => void;
  onTaskComplete: (accountId: number, status: string) => void;
}

interface LogEntry {
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

// Determine log level from message content
function detectLogLevel(message: string): 'info' | 'success' | 'warning' | 'error' {
  const lowerMsg = message.toLowerCase();
  if (lowerMsg.includes('error') || lowerMsg.includes('failed')) return 'error';
  if (lowerMsg.includes('warning') || lowerMsg.includes('warn') || lowerMsg.includes('may need')) return 'warning';
  if (lowerMsg.includes('complete') || lowerMsg.includes('saved') || lowerMsg.includes('kept') || lowerMsg.includes('+ ')) return 'success';
  return 'info';
}

export default function AccountCardWithConsole({
  account,
  activeTask,
  onRefresh,
  onTaskComplete
}: AccountCardWithConsoleProps) {
  const [loading, setLoading] = useState(false);

  // Console log state
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [taskStatus, setTaskStatus] = useState<string>('running');
  const containerRef = useRef<HTMLDivElement>(null);

  // Account stats state
  const [stats, setStats] = useState<AccountStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Handle task completion
  const handleComplete = useCallback((status: string) => {
    onTaskComplete(account.account_id, status);
  }, [account.account_id, onTaskComplete]);

  // Load account stats with auto-refresh every 30 seconds
  useEffect(() => {
    const loadStats = async () => {
      try {
        const accountStats = await getAccountStats(account.account_id);
        setStats(accountStats);
      } catch (error) {
        console.error('Failed to load account stats:', error);
      } finally {
        setStatsLoading(false);
      }
    };

    loadStats();
    const interval = setInterval(loadStats, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, [account.account_id]);

  // SSE connection for logs
  useEffect(() => {
    if (!activeTask) {
      setLogs([]);
      setTaskStatus('running');
      return;
    }

    const apiHost = window.location.hostname;
    const eventSource = new EventSource(`http://${apiHost}:8000/api/scrape/logs/${activeTask.taskId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'log') {
          const timestamp = new Date().toLocaleTimeString();
          const level = detectLogLevel(data.message);
          setLogs((prev) => [...prev, { timestamp, level, message: data.message }]);
        } else if (data.type === 'status') {
          setTaskStatus(data.status);
          if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
            eventSource.close();
            handleComplete(data.status);
          }
        }
      } catch (e) {
        console.error('Failed to parse log:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setTaskStatus('error');
      handleComplete('error');
    };

    return () => {
      eventSource.close();
    };
  }, [activeTask, handleComplete]);

  // Auto-scroll console to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

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

  const handleStopTask = async () => {
    if (!activeTask) return;
    try {
      await cancelScrape(activeTask.taskId);
    } catch (error) {
      console.error('Cancel failed:', error);
      alert(error instanceof Error ? error.message : 'Failed to cancel');
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'success': return 'text-emerald-300';
      case 'warning': return 'text-amber-300';
      case 'error': return 'text-red-300';
      default: return 'text-blue-300';
    }
  };

  const getLevelLabel = (level: string) => {
    switch (level) {
      case 'success': return '[SUCCESS]';
      case 'warning': return '[WARN]';
      case 'error': return '[ERROR]';
      default: return '[INFO]';
    }
  };

  return (
    <div className={`bg-stone-800 rounded-xl border transition-all ${
      activeTask ? 'border-[rgba(217,119,87,0.4)]' : 'border-stone-700 hover:border-stone-600'
    }`}>
      {/* Account Card Header */}
      <div className="p-5">
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
          <div className="flex items-center gap-2">
            {activeTask && (
              <span className="font-mono text-xs px-2 py-1 rounded bg-[rgba(217,119,87,0.15)] text-[#E8A090] border border-[rgba(217,119,87,0.25)]">
                SCRAPING
              </span>
            )}
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
        </div>

        {/* Current Task Info */}
        {activeTask && (
          <div className="mb-4 p-3 bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.2)] rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs text-stone-500 font-mono uppercase">Scraping:</span>
                <span className="ml-2 text-sm text-[#E8A090] font-medium">{activeTask.keyword}</span>
              </div>
              <button
                onClick={handleStopTask}
                className="px-3 py-1.5 bg-[rgba(239,68,68,0.2)] text-red-300 border border-[rgba(239,68,68,0.3)] text-xs font-medium rounded transition-all hover:bg-[rgba(239,68,68,0.3)]"
              >
                Stop
              </button>
            </div>
          </div>
        )}

        {/* Account Stats - Only show when not actively scraping */}
        {!activeTask && (
          <div className="mb-4">
            <AccountStatsDisplay stats={stats} loading={statsLoading} />
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {account.browser_open ? (
            <button
              onClick={handleCloseBrowser}
              disabled={loading || !!activeTask}
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
            disabled={loading || !!activeTask}
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

      {/* Console Log Section - Only shows when task is active */}
      {activeTask && (
        <div className="border-t border-stone-700">
          {/* Console Header */}
          <div className="px-4 py-2 border-b border-stone-700 flex items-center justify-between bg-black/30">
            <span className="font-mono text-xs text-stone-500 uppercase tracking-widest">
              Console
            </span>
            <span className={`font-mono text-xs px-2 py-0.5 rounded ${
              taskStatus === 'running'
                ? 'bg-[rgba(217,119,87,0.15)] text-[#E8A090] border border-[rgba(217,119,87,0.25)]'
                : taskStatus === 'completed'
                ? 'bg-[rgba(16,185,129,0.15)] text-emerald-300 border border-[rgba(16,185,129,0.25)]'
                : 'bg-[rgba(239,68,68,0.15)] text-red-300 border border-[rgba(239,68,68,0.25)]'
            }`}>
              {taskStatus.toUpperCase()}
            </span>
          </div>

          {/* Log Output */}
          <div
            ref={containerRef}
            className="p-4 max-h-48 overflow-y-auto font-mono text-xs leading-relaxed bg-black/20"
            aria-live="polite"
            aria-atomic="false"
            role="log"
          >
            {logs.length === 0 ? (
              <div className="text-stone-600">Waiting for logs...</div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className="flex gap-2">
                  <span className="text-stone-600 shrink-0">{log.timestamp}</span>
                  <span className={`shrink-0 ${getLevelColor(log.level)}`}>
                    {getLevelLabel(log.level)}
                  </span>
                  <span className="text-stone-400">{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
