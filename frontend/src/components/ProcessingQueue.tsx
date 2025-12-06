// Processing Queue - Shows tasks being processed in the wash queue
// Version: 1.5 - Applied consistent font-mono styling to headers and counts
// Changes: Step title uses font-mono, task counts and file totals use font-mono
// Previous: Changed Cancel to Stop button, show duration on completion

'use client';

import { useState, useEffect } from 'react';
import { CleaningTask } from './WashingMachine';

interface ProcessingQueueProps {
  tasks: CleaningTask[];
  onCancelTask?: (taskId: string) => void;
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
  };

  const config = statusConfig[status];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.color}`}>
      {config.text}
    </span>
  );
}

// Single task card component
function TaskCard({
  task,
  onCancel,
}: {
  task: CleaningTask;
  onCancel?: () => void;
}) {
  const [elapsedTime, setElapsedTime] = useState('—');

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
          {task.files.slice(0, 3).map((file, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 bg-stone-800 rounded text-xs text-stone-400 truncate max-w-[120px]"
              title={file}
            >
              {file}
            </span>
          ))}
          {task.files.length > 3 && (
            <span className="px-1.5 py-0.5 text-xs text-stone-500">
              +{task.files.length - 3} more
            </span>
          )}
        </div>
      </div>

      {/* Animated processing indicator */}
      {task.status === 'processing' && (
        <div className="mb-2 py-2 px-3 bg-[rgba(59,130,246,0.1)] rounded-lg">
          <p className="text-sm text-blue-300 font-medium">
            Processing<AnimatedDots />
          </p>
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
    </div>
  );
}

export default function ProcessingQueue({ tasks, onCancelTask }: ProcessingQueueProps) {
  // Separate tasks by status
  const processingTasks = tasks.filter(t => t.status === 'processing');
  const queuedTasks = tasks.filter(t => t.status === 'queued');
  const completedTasks = tasks.filter(t => t.status === 'completed' || t.status === 'failed');

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

      {/* Task list */}
      <div className="p-3 max-h-[400px] overflow-y-auto space-y-2">
        {/* Processing tasks first */}
        {processingTasks.map(task => (
          <TaskCard
            key={task.id}
            task={task}
            onCancel={onCancelTask ? () => onCancelTask(task.id) : undefined}
          />
        ))}

        {/* Queued tasks */}
        {queuedTasks.map(task => (
          <TaskCard
            key={task.id}
            task={task}
            onCancel={onCancelTask ? () => onCancelTask(task.id) : undefined}
          />
        ))}

        {/* Separator if there are completed tasks */}
        {completedTasks.length > 0 && (processingTasks.length > 0 || queuedTasks.length > 0) && (
          <div className="flex items-center gap-2 py-2">
            <div className="flex-1 h-px bg-stone-700" />
            <span className="text-xs text-stone-500">Completed</span>
            <div className="flex-1 h-px bg-stone-700" />
          </div>
        )}

        {/* Completed/failed tasks */}
        {completedTasks.slice(0, 5).map(task => (
          <TaskCard key={task.id} task={task} />
        ))}

        {completedTasks.length > 5 && (
          <p className="text-xs text-stone-500 text-center py-2">
            +{completedTasks.length - 5} more completed tasks
          </p>
        )}
      </div>
    </div>
  );
}
