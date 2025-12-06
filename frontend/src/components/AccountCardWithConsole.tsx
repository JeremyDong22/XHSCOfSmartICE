// Account card component with embedded console log for active scrape tasks
// Version: 1.2 - Added inline nickname editing with pen icon
// Changes: Added edit mode for account alias with pen icon, saves to backend permanently
// Previous: Integrated AccountStatsDisplay component with auto-refresh every 30s

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Account, AccountStats, openBrowser, closeBrowser, deleteAccount, cancelScrape, getAccountStats, updateAccount } from '@/lib/api';
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

  // Nickname editing state
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(account.nickname || '');
  const [savingName, setSavingName] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);

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

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditingName && nameInputRef.current) {
      nameInputRef.current.focus();
      nameInputRef.current.select();
    }
  }, [isEditingName]);

  // Update editedName when account.nickname changes externally
  useEffect(() => {
    setEditedName(account.nickname || '');
  }, [account.nickname]);

  const handleStartEditing = () => {
    setEditedName(account.nickname || '');
    setIsEditingName(true);
  };

  const handleCancelEditing = () => {
    setEditedName(account.nickname || '');
    setIsEditingName(false);
  };

  const handleSaveName = async () => {
    const trimmedName = editedName.trim();
    if (trimmedName === account.nickname) {
      setIsEditingName(false);
      return;
    }

    setSavingName(true);
    try {
      await updateAccount(account.account_id, { nickname: trimmedName });
      setIsEditingName(false);
      onRefresh();
    } catch (error) {
      console.error('Failed to save nickname:', error);
      alert('保存昵称失败');
    } finally {
      setSavingName(false);
    }
  };

  const handleNameKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSaveName();
    } else if (e.key === 'Escape') {
      handleCancelEditing();
    }
  };

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
      alert('打开浏览器失败');
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
      alert('关闭浏览器失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`确定删除账号 ${account.account_id}？此操作无法撤销。`)) return;

    setLoading(true);
    try {
      await deleteAccount(account.account_id);
      onRefresh();
    } catch (error) {
      console.error('Failed to delete account:', error);
      alert('删除账号失败');
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
              {isEditingName ? (
                <div className="flex items-center gap-1">
                  <input
                    ref={nameInputRef}
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    onKeyDown={handleNameKeyDown}
                    onBlur={handleSaveName}
                    disabled={savingName}
                    placeholder={`Account ${account.account_id}`}
                    className="bg-stone-700 border border-stone-500 rounded px-2 py-0.5 text-sm text-stone-50 font-medium focus:outline-none focus:border-[#D97757] w-32"
                  />
                  {savingName && (
                    <svg className="animate-spin h-4 w-4 text-stone-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-1.5 group">
                  <span className="font-medium text-stone-50">
                    {account.nickname || `Account ${account.account_id}`}
                  </span>
                  <button
                    onClick={handleStartEditing}
                    className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-stone-700 transition-all"
                    title="编辑昵称"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5 text-stone-400 hover:text-stone-200" viewBox="0 0 20 20" fill="currentColor">
                      <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                    </svg>
                  </button>
                </div>
              )}
              <div className="font-mono text-xs text-stone-500">
                ID: {account.account_id}
              </div>
            </div>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2">
            {activeTask && (
              <span className="font-mono text-xs px-2 py-1 rounded bg-[rgba(217,119,87,0.15)] text-[#E8A090] border border-[rgba(217,119,87,0.25)]">
                采集中
              </span>
            )}
            {account.browser_open ? (
              <span className="font-mono text-xs px-2 py-1 rounded bg-[rgba(16,185,129,0.15)] text-emerald-300 border border-[rgba(16,185,129,0.25)]">
                在线
              </span>
            ) : (
              <span className="font-mono text-xs px-2 py-1 rounded bg-[rgba(120,113,108,0.15)] text-stone-400 border border-[rgba(120,113,108,0.25)]">
                离线
              </span>
            )}
          </div>
        </div>

        {/* Current Task Info */}
        {activeTask && (
          <div className="mb-4 p-3 bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.2)] rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs text-stone-500 font-mono uppercase">采集关键词:</span>
                <span className="ml-2 text-sm text-[#E8A090] font-medium">{activeTask.keyword}</span>
              </div>
              <button
                onClick={handleStopTask}
                className="px-3 py-1.5 bg-[rgba(239,68,68,0.2)] text-red-300 border border-[rgba(239,68,68,0.3)] text-xs font-medium rounded transition-all hover:bg-[rgba(239,68,68,0.3)]"
              >
                停止
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
              关闭浏览器
            </button>
          ) : (
            <button
              onClick={handleOpenBrowser}
              disabled={loading}
              className="flex-1 px-4 py-2 bg-[#D97757] text-white rounded-lg text-sm font-medium transition-all hover:bg-[#E8886A] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              打开浏览器
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={loading || !!activeTask}
            className="px-3 py-2 bg-[rgba(239,68,68,0.2)] text-red-300 border border-[rgba(239,68,68,0.3)] rounded-lg transition-all hover:bg-[rgba(239,68,68,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
            title="删除账号"
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
              控制台
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
              <div className="text-stone-600">等待日志...</div>
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
