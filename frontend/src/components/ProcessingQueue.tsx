// Processing Queue - Shows tasks being processed in the wash queue
// Version: 1.7 - Added rate_limited status styling and warning display
// Changes: Added amber/orange styling for rate limited tasks, warning message panel
// Previous: Added 2-column grid layout and foldable log console

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { CleaningTask } from './WashingMachine';
import { subscribeToCleaningLogs } from '@/lib/api';

interface ProcessingQueueProps {
  tasks: CleaningTask[];
  onCancelTask?: (taskId: string) => void;
  // Map of frontend task ID to backend task ID (for SSE subscription)
  backendTaskIds?: Map<string, string>;
}

// Format elapsed time since task started
function formatElapsedTime(startedAt?: Date): string {
  if (!startedAt) return '—';

  const now = new Date();
  const elapsed = Math.floor((now.getTime() - startedAt.getTime()) / 1000);

  if (elapsed < 60) {
    return `${elapsed}s`;
  } else if (elapsed < 3600) {
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    return `${mins}m ${secs}s`;
  } else {
    const hours = Math.floor(elapsed / 3600);
    const mins = Math.floor((elapsed % 3600) / 60);
    return `${hours}h ${mins}m`;
  }
}

// Format start time
function formatStartTime(date?: Date): string {
  if (!date) return '—';
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// Calculate duration between two dates
function formatDuration(startedAt?: Date, completedAt?: Date): string {
  if (!startedAt || !completedAt) return '—';

  const elapsed = Math.floor((completedAt.getTime() - startedAt.getTime()) / 1000);

  if (elapsed < 60) {
    return `${elapsed}s`;
  } else if (elapsed < 3600) {
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    return `${mins}m ${secs}s`;
  } else {
    const hours = Math.floor(elapsed / 3600);
    const mins = Math.floor((elapsed % 3600) / 60);
    return `${hours}h ${mins}m`;
  }
}

// Animated dots component for processing state
function AnimatedDots() {
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    return () => clearInterval(interval);
  }, []);

  return (
    <span className="inline-block w-4 text-left">{dots}</span>
  );
}

// Status badge component
function StatusBadge({ status }: { status: CleaningTask['status'] }) {
  const statusConfig = {
    queued: { text: 'Queued', bg: 'bg-stone-700', color: 'text-stone-300' },
    processing: { text: 'Processing', bg: 'bg-[rgba(59,130,246,0.2)]', color: 'text-blue-300' },
    completed: { text: 'Completed', bg: 'bg-[rgba(16,185,129,0.2)]', color: 'text-emerald-300' },
    failed: { text: 'Failed', bg: 'bg-[rgba(239,68,68,0.2)]', color: 'text-red-300' },
    rate_limited: { text: '⚠️ Rate Limited', bg: 'bg-[rgba(245,158,11,0.2)]', color: 'text-amber-300' },
  };

  const config = statusConfig[status];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.color}`}>
      {config.text}
    </span>
  );
}

// Single task card component with foldable log console
function TaskCard({
  task,
  onCancel,
  backendTaskId,
}: {
  task: CleaningTask;
  onCancel?: () => void;
  backendTaskId?: string;
}) {
  const [elapsedTime, setElapsedTime] = useState('—');
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // Subscribe to logs when task is processing
  useEffect(() => {
    if (task.status !== 'processing' || !backendTaskId) return;

    // Auto-expand when processing starts
    setLogsExpanded(true);

    const cleanup = subscribeToCleaningLogs(
      backendTaskId,
      (message) => {
        setLogs(prev => [...prev, message]);
      }
    );
    cleanupRef.current = cleanup;

    return () => {
      cleanup();
      cleanupRef.current = null;
    };
  }, [task.status, backendTaskId]);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (logContainerRef.current && logsExpanded) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, logsExpanded]);

  // Update elapsed time every second for processing tasks
  useEffect(() => {
    if (task.status !== 'processing' || !task.startedAt) return;

    const interval = setInterval(() => {
      setElapsedTime(formatElapsedTime(task.startedAt));
    }, 1000);

    // Initial update
    setElapsedTime(formatElapsedTime(task.startedAt));

    return () => clearInterval(interval);
  }, [task.status, task.startedAt]);

  // Get operation summary
  const getOperationSummary = () => {
    const ops: string[] = [];
    if (task.config.filterBy.enabled) {
      const { metric, operator, value } = task.config.filterBy;
      const opSymbol = operator === 'gte' ? '≥' : operator === 'gt' ? '>' : operator === 'lte' ? '≤' : '<';
      ops.push(`Filter: ${metric} ${opSymbol} ${value}`);
    }
    if (task.config.labelBy.enabled) {
      const targets: string[] = [];
      if (task.config.labelBy.imageTarget) targets.push(task.config.labelBy.imageTarget);
      if (task.config.labelBy.textTarget) targets.push(task.config.labelBy.textTarget);
      ops.push(`Label: ${targets.join(', ')} (${task.config.labelBy.labelCount} labels)`);
    }
    return ops.join(' | ');
  };

  return (
    <div className={`bg-stone-900 rounded-lg border p-3 transition-all ${
      task.status === 'processing'
        ? 'border-[rgba(59,130,246,0.3)]'
        : task.status === 'completed'
          ? 'border-[rgba(16,185,129,0.3)]'
          : task.status === 'failed'
            ? 'border-[rgba(239,68,68,0.3)]'
            : task.status === 'rate_limited'
              ? 'border-[rgba(245,158,11,0.3)]'
              : 'border-stone-700'
    }`}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={task.status} />
          <span className="text-xs text-stone-500 font-mono">{task.id}</span>
        </div>
        {task.status === 'processing' && onCancel && (
          <button
            onClick={onCancel}
            className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded bg-[rgba(239,68,68,0.1)] hover:bg-[rgba(239,68,68,0.2)] transition-colors"
            title="Stop processing"
          >
            {/* Stop sign (octagon) icon */}
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86L7.86 2zM8 7v10h8V7H8z" />
            </svg>
            Stop
          </button>
        )}
      </div>

      {/* Operations summary */}
      <p className="text-xs text-stone-400 mb-2">{getOperationSummary()}</p>

      {/* Files list */}
      <div className="mb-2">
        <p className="text-xs text-stone-500 mb-1">Files ({task.files.length}):</p>
        <div className="flex flex-wrap gap-1">
          {task.files.slice(0, 2).map((file, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 bg-stone-800 rounded text-xs text-stone-400 truncate max-w-[100px]"
              title={file}
            >
              {file}
            </span>
          ))}
          {task.files.length > 2 && (
            <span className="px-1.5 py-0.5 text-xs text-stone-500">
              +{task.files.length - 2} more
            </span>
          )}
        </div>
      </div>

      {/* Foldable Log Console */}
      {(task.status === 'processing' || logs.length > 0) && (
        <div className="mb-2">
          <button
            onClick={() => setLogsExpanded(!logsExpanded)}
            className="flex items-center gap-1.5 text-xs text-stone-400 hover:text-stone-300 transition-colors mb-1"
          >
            <svg
              className={`w-3 h-3 transition-transform ${logsExpanded ? 'rotate-90' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
            <span className="font-mono">Logs ({logs.length})</span>
          </button>

          {logsExpanded && (
            <div
              ref={logContainerRef}
              className="bg-stone-950 rounded border border-stone-800 p-2 max-h-32 overflow-y-auto font-mono text-xs"
            >
              {logs.length === 0 ? (
                <p className="text-stone-600 italic">Waiting for logs...</p>
              ) : (
                logs.map((log, i) => (
                  <div
                    key={i}
                    className={`py-0.5 ${
                      log.startsWith('✓') ? 'text-emerald-400' :
                      log.startsWith('✗') ? 'text-red-400' :
                      log.includes('- processing') ? 'text-blue-300' :
                      log.includes('- done') ? 'text-emerald-300' :
                      'text-stone-400'
                    }`}
                  >
                    {log}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Timing info */}
      <div className="flex items-center justify-between text-xs text-stone-500">
        <span>
          {task.status === 'completed'
            ? `Completed at ${formatStartTime(task.completedAt)}`
            : `Started: ${task.startedAt ? formatStartTime(task.startedAt) : 'Waiting...'}`
          }
        </span>
        {task.status === 'processing' && (
          <span className="text-blue-300 font-mono">{elapsedTime}</span>
        )}
        {task.status === 'completed' && task.completedAt && task.startedAt && (
          <span className="text-emerald-400 font-medium">
            Duration: {formatDuration(task.startedAt, task.completedAt)}
          </span>
        )}
      </div>

      {/* Error message for failed tasks */}
      {task.status === 'failed' && task.error && (
        <div className="mt-2 p-2 bg-[rgba(239,68,68,0.1)] rounded text-xs text-red-300">
          {task.error}
        </div>
      )}

      {/* Rate limit warning for rate_limited tasks */}
      {task.status === 'rate_limited' && task.error && (
        <div className="mt-2 p-2 bg-[rgba(245,158,11,0.1)] rounded text-xs text-amber-300">
          {task.error}
        </div>
      )}
    </div>
  );
}

export default function ProcessingQueue({ tasks, onCancelTask, backendTaskIds }: ProcessingQueueProps) {
  // Separate tasks by status
  const processingTasks = tasks.filter(t => t.status === 'processing');
  const queuedTasks = tasks.filter(t => t.status === 'queued');
  const completedTasks = tasks.filter(t => t.status === 'completed' || t.status === 'failed' || t.status === 'rate_limited');

  // All active tasks (for grid display)
  const activeTasks = [...processingTasks, ...queuedTasks];

  // Calculate total stats
  const totalFiles = tasks.reduce((acc, t) => acc + t.files.length, 0);

  if (tasks.length === 0) {
    return (
      <div className="bg-stone-800 rounded-xl border border-stone-700 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">3</span>
          </div>
          <div>
            <h3 className="text-sm font-mono font-semibold text-stone-50 tracking-tight">Cleaning Queue</h3>
            <p className="text-xs text-stone-500">No tasks in queue</p>
          </div>
        </div>
        <div className="text-center py-6 text-stone-500 text-sm">
          <p>Add tasks from the Washing Machine to start processing.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-stone-800 rounded-xl border border-stone-700 overflow-hidden">
      {/* Header with stats */}
      <div className="p-4 border-b border-stone-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-sm">3</span>
            </div>
            <div>
              <h3 className="text-sm font-mono font-semibold text-stone-50 tracking-tight">Cleaning Queue</h3>
              <p className="text-xs font-mono text-stone-500">
                {processingTasks.length} processing · {queuedTasks.length} queued
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-stone-500">Total files</p>
            <p className="text-sm font-mono text-stone-300">{totalFiles}</p>
          </div>
        </div>
      </div>

      {/* Task grid - 2 columns at 50% width each */}
      <div className="p-3 max-h-[500px] overflow-y-auto">
        {/* Active tasks in 2-column grid */}
        {activeTasks.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {activeTasks.map(task => (
              <TaskCard
                key={task.id}
                task={task}
                onCancel={onCancelTask ? () => onCancelTask(task.id) : undefined}
                backendTaskId={backendTaskIds?.get(task.id)}
              />
            ))}
          </div>
        )}

        {/* Separator if there are completed tasks */}
        {completedTasks.length > 0 && activeTasks.length > 0 && (
          <div className="flex items-center gap-2 py-3 mt-3">
            <div className="flex-1 h-px bg-stone-700" />
            <span className="text-xs text-stone-500">Completed</span>
            <div className="flex-1 h-px bg-stone-700" />
          </div>
        )}

        {/* Completed/failed tasks in 2-column grid */}
        {completedTasks.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {completedTasks.slice(0, 6).map(task => (
              <TaskCard
                key={task.id}
                task={task}
                backendTaskId={backendTaskIds?.get(task.id)}
              />
            ))}
          </div>
        )}

        {completedTasks.length > 6 && (
          <p className="text-xs text-stone-500 text-center py-2 mt-2">
            +{completedTasks.length - 6} more completed tasks
          </p>
        )}
      </div>
    </div>
  );
}
