// Data Cleaning Tab - Main container for the "Data Laundry" feature
// Version: 3.0 - Sync left panel height with right WashingMachine height
// Changes: Left panel height matches right panel, scrolls when content overflows
// Previous: handleCancelTask now calls backend API to cancel running tasks

'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import ScrapeResultsPanel, { EnrichedResultFile } from './ScrapeResultsPanel';
import WashingMachine, { CleaningTask } from './WashingMachine';
import ProcessingQueue from './ProcessingQueue';
import CleanedResultsViewer, { CleanedResultFile, CleanedResultData } from './CleanedResultsViewer';
import {
  startCleaning,
  getCleaningTaskStatus,
  getCleanedResults,
  getCleanedResult,
  getCleaningTasks,
  getAccounts,
  cancelCleaningTask,
  deleteCleaningTask,
  Account,
  CleaningRequest,
  CleanedResultFile as ApiCleanedResultFile,
  CleaningTaskFull,
  CleaningConfigStored,
} from '@/lib/api';

export default function DataCleaningTab() {
  // Accounts for nickname lookup
  const [accounts, setAccounts] = useState<Account[]>([]);

  // Selected files from the left panel
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);

  // Available files from scrape results
  const [availableFiles, setAvailableFiles] = useState<EnrichedResultFile[]>([]);

  // Task queue
  const [tasks, setTasks] = useState<CleaningTask[]>([]);

  // Cleaned results (mock data for now - will be populated from backend)
  const [cleanedFiles, setCleanedFiles] = useState<CleanedResultFile[]>([]);
  const [selectedCleanedData, setSelectedCleanedData] = useState<CleanedResultData | null>(null);
  const [loadingCleanedData, setLoadingCleanedData] = useState(false);

  // Track polling intervals for cleanup - maps frontend task.id -> backend task_id
  const pollingIntervalsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const backendTaskIdsRef = useRef<Map<string, string>>(new Map());

  // Refs for syncing panel heights - right panel determines the max height
  const rightPanelRef = useRef<HTMLDivElement>(null);
  const [rightPanelHeight, setRightPanelHeight] = useState<number | null>(null);

  // Helper: Convert backend task to frontend CleaningTask format
  const convertBackendTask = useCallback((backendTask: CleaningTaskFull): CleaningTask => {
    return {
      id: backendTask.id,
      files: backendTask.files,
      config: {
        filterBy: {
          enabled: backendTask.config.filterBy.enabled,
          metric: backendTask.config.filterBy.metric as 'likes' | 'collects' | 'comments',
          operator: backendTask.config.filterBy.operator as 'gte' | 'lte' | 'gt' | 'lt',
          value: backendTask.config.filterBy.value,
        },
        labelBy: {
          enabled: backendTask.config.labelBy.enabled,
          imageTarget: backendTask.config.labelBy.imageTarget as 'cover_image' | 'images' | null,
          textTarget: backendTask.config.labelBy.textTarget as 'title' | 'content' | null,
          userDescription: backendTask.config.labelBy.userDescription,
          fullPrompt: backendTask.config.labelBy.fullPrompt,
        },
      },
      status: backendTask.status,
      startedAt: backendTask.started_at ? new Date(backendTask.started_at) : undefined,
      completedAt: backendTask.completed_at ? new Date(backendTask.completed_at) : undefined,
      progress: backendTask.progress,
      error: backendTask.error,
    };
  }, []);

  // Cleanup polling intervals on unmount
  useEffect(() => {
    return () => {
      pollingIntervalsRef.current.forEach((interval) => clearInterval(interval));
      pollingIntervalsRef.current.clear();
    };
  }, []);

  // Sync left panel height with right panel using ResizeObserver
  useEffect(() => {
    const rightPanel = rightPanelRef.current;
    if (!rightPanel) return;

    const updateHeight = () => {
      setRightPanelHeight(rightPanel.offsetHeight);
    };

    // Initial measurement
    updateHeight();

    // Observe size changes
    const resizeObserver = new ResizeObserver(updateHeight);
    resizeObserver.observe(rightPanel);

    return () => resizeObserver.disconnect();
  }, []);

  // Load accounts on mount for nickname display
  useEffect(() => {
    const loadAccounts = async () => {
      try {
        const accountsData = await getAccounts();
        setAccounts(accountsData);
      } catch (err) {
        console.error('Failed to load accounts:', err);
      }
    };
    loadAccounts();
  }, []);

  // Handle files loaded from scrape results panel
  const handleFilesLoaded = useCallback((files: EnrichedResultFile[]) => {
    setAvailableFiles(files);
  }, []);

  // Load cleaned results from backend on mount and after task completion
  const loadCleanedResults = useCallback(async () => {
    try {
      const results = await getCleanedResults();
      const mappedFiles: CleanedResultFile[] = results.map((r: ApiCleanedResultFile) => ({
        filename: r.filename,
        size: r.size,
        cleanedAt: new Date(r.cleaned_at),
      }));
      setCleanedFiles(mappedFiles);
    } catch (err) {
      console.error('Failed to load cleaned results:', err);
    }
  }, []);

  useEffect(() => {
    loadCleanedResults();
  }, [loadCleanedResults]);

  // Poll for task status until completed or failed
  const pollTaskStatus = useCallback(async (frontendTaskId: string, backendTaskId: string) => {
    const POLL_INTERVAL = 2000; // Poll every 2 seconds

    const poll = async () => {
      try {
        const status = await getCleaningTaskStatus(backendTaskId);

        if (status.status === 'completed') {
          // Stop polling
          const interval = pollingIntervalsRef.current.get(frontendTaskId);
          if (interval) {
            clearInterval(interval);
            pollingIntervalsRef.current.delete(frontendTaskId);
          }

          // Mark as completed
          setTasks(prev => prev.map(t =>
            t.id === frontendTaskId
              ? { ...t, status: 'completed' as const, progress: 100, completedAt: new Date() }
              : t
          ));

          // Reload cleaned results to show the new file
          await loadCleanedResults();

        } else if (status.status === 'failed') {
          // Stop polling
          const interval = pollingIntervalsRef.current.get(frontendTaskId);
          if (interval) {
            clearInterval(interval);
            pollingIntervalsRef.current.delete(frontendTaskId);
          }

          // Mark as failed
          setTasks(prev => prev.map(t =>
            t.id === frontendTaskId
              ? { ...t, status: 'failed' as const, error: status.error || 'Unknown error' }
              : t
          ));
        } else if (status.status === 'rate_limited') {
          // Stop polling
          const interval = pollingIntervalsRef.current.get(frontendTaskId);
          if (interval) {
            clearInterval(interval);
            pollingIntervalsRef.current.delete(frontendTaskId);
          }

          // Mark as rate_limited (task paused due to API quota)
          setTasks(prev => prev.map(t =>
            t.id === frontendTaskId
              ? { ...t, status: 'rate_limited' as const, error: status.error || 'API rate limit reached' }
              : t
          ));
        }
        // If still processing, continue polling (interval will fire again)
      } catch (err) {
        console.error('Error polling task status:', err);
        // Continue polling on error - backend might be temporarily unavailable
      }
    };

    // Start polling
    const interval = setInterval(poll, POLL_INTERVAL);
    pollingIntervalsRef.current.set(frontendTaskId, interval);

    // Also do an immediate poll
    await poll();
  }, [loadCleanedResults]);

  // Load tasks from backend on mount (page refresh recovery)
  useEffect(() => {
    const loadTasks = async () => {
      try {
        const backendTasks = await getCleaningTasks();
        if (backendTasks.length === 0) return;

        // Convert and set tasks
        const convertedTasks = backendTasks.map(convertBackendTask);
        setTasks(convertedTasks);

        // Store backend task IDs for polling
        backendTasks.forEach(bt => {
          backendTaskIdsRef.current.set(bt.id, bt.backend_task_id);
        });

        // Note: We don't resume polling for "processing" tasks because the backend
        // already marks them as failed on restart (server restart = task interrupted)
        console.log(`Restored ${convertedTasks.length} tasks from backend`);
      } catch (err) {
        console.error('Failed to load tasks from backend:', err);
      }
    };

    loadTasks();
  }, [convertBackendTask]);

  // Handle task submission from washing machine - calls real backend API
  const handleTaskSubmit = useCallback(async (task: CleaningTask) => {
    // Add task to queue with queued status
    setTasks(prev => [...prev, task]);

    // Clear selection after submission
    setSelectedFiles([]);

    // Build frontend_config for persistent storage on backend
    const frontendConfig: CleaningConfigStored = {
      filterBy: {
        enabled: task.config.filterBy.enabled,
        metric: task.config.filterBy.metric,
        operator: task.config.filterBy.operator,
        value: task.config.filterBy.value,
      },
      labelBy: {
        enabled: task.config.labelBy.enabled,
        imageTarget: task.config.labelBy.imageTarget,
        textTarget: task.config.labelBy.textTarget,
        userDescription: task.config.labelBy.userDescription,
        fullPrompt: task.config.labelBy.fullPrompt,
      },
    };

    const request: CleaningRequest = {
      source_files: task.files,
      filter_by: task.config.filterBy.enabled ? {
        metric: task.config.filterBy.metric,
        operator: task.config.filterBy.operator,
        value: task.config.filterBy.value,
      } : null,
      label_by: task.config.labelBy.enabled ? {
        image_target: task.config.labelBy.imageTarget,
        text_target: task.config.labelBy.textTarget,
        user_description: task.config.labelBy.userDescription,
        full_prompt: task.config.labelBy.fullPrompt,
      } : null,
      // Add frontend task ID and config for persistent storage
      frontend_task_id: task.id,
      frontend_config: frontendConfig,
    };

    try {
      // Call the backend API FIRST to get task_id before marking as processing
      // This ensures SSE subscription can happen when status changes to 'processing'
      const response = await startCleaning(request);

      // Store the backend task_id mapping BEFORE changing status
      const backendTaskId = (response as unknown as { task_id: string }).task_id;
      backendTaskIdsRef.current.set(task.id, backendTaskId);

      // NOW mark task as processing (SSE subscription will work since backendTaskId is set)
      setTasks(prev => prev.map(t =>
        t.id === task.id
          ? { ...t, status: 'processing' as const, startedAt: new Date(), progress: 10 }
          : t
      ));

      // Start polling for task completion
      await pollTaskStatus(task.id, backendTaskId);

    } catch (err) {
      console.error('Cleaning task failed:', err);
      // Mark task as failed
      setTasks(prev => prev.map(t =>
        t.id === task.id
          ? { ...t, status: 'failed' as const, error: err instanceof Error ? err.message : 'Unknown error' }
          : t
      ));
    }
  }, [pollTaskStatus]);

  // Handle task cancellation - calls backend API to stop running task
  const handleCancelTask = useCallback(async (taskId: string) => {
    // Get the backend task ID
    const backendTaskId = backendTaskIdsRef.current.get(taskId);

    if (backendTaskId) {
      try {
        // Call backend API to cancel the task
        await cancelCleaningTask(backendTaskId);
        console.log(`Cancelled task ${taskId} (backend: ${backendTaskId})`);
      } catch (err) {
        console.error('Failed to cancel task:', err);
        // Still continue with frontend cleanup
      }
    }

    // Stop polling for this task
    const interval = pollingIntervalsRef.current.get(taskId);
    if (interval) {
      clearInterval(interval);
      pollingIntervalsRef.current.delete(taskId);
    }

    // Mark task as failed in UI (instead of removing)
    setTasks(prev => prev.map(t =>
      t.id === taskId
        ? { ...t, status: 'failed' as const, error: 'Cancelled by user', completedAt: new Date() }
        : t
    ));
  }, []);

  // Handle task deletion - removes completed/failed tasks from history
  const handleDeleteTask = useCallback(async (taskId: string) => {
    try {
      // Call backend API to delete from persistent storage
      await deleteCleaningTask(taskId);
      console.log(`Deleted task ${taskId}`);
    } catch (err) {
      console.error('Failed to delete task from backend:', err);
      // Still remove from frontend
    }

    // Remove from frontend state
    backendTaskIdsRef.current.delete(taskId);
    setTasks(prev => prev.filter(t => t.id !== taskId));
  }, []);

  // Handle cleaned file selection - load real data from backend API
  const handleCleanedFileSelect = useCallback(async (filename: string) => {
    setLoadingCleanedData(true);

    try {
      const data = await getCleanedResult(filename);

      // Map API response to frontend format
      const mappedData: CleanedResultData = {
        metadata: {
          cleanedAt: data.metadata.cleaned_at,
          processedBy: data.metadata.processed_by,
          processingTime: data.metadata.processing_time_seconds,
          filterByCondition: data.metadata.filter_by_condition
            ? {
                metric: data.metadata.filter_by_condition.metric,
                operator: data.metadata.filter_by_condition.operator,
                value: data.metadata.filter_by_condition.value,
              }
            : undefined,
          labelByCondition: data.metadata.label_by_condition
            ? {
                imageTarget: data.metadata.label_by_condition.image_target,
                textTarget: data.metadata.label_by_condition.text_target,
                userDescription: data.metadata.label_by_condition.user_description,
                fullPrompt: data.metadata.label_by_condition.full_prompt,
              }
            : undefined,
          originalFiles: data.metadata.original_files,
          totalPostsInput: data.metadata.total_posts_input,
          totalPostsOutput: data.metadata.total_posts_output,
        },
        posts: data.posts,
      };

      setSelectedCleanedData(mappedData);
    } catch (err) {
      console.error('Failed to load cleaned result:', err);
      setSelectedCleanedData(null);
    } finally {
      setLoadingCleanedData(false);
    }
  }, []);

  // Count active tasks
  const activeTasks = tasks.filter(t => t.status === 'processing' || t.status === 'queued');

  return (
    <div className="space-y-6">
      {/* Header description */}
      <div className="bg-stone-800 rounded-xl border border-stone-700 p-5">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="2" width="20" height="20" rx="3" />
              <circle cx="12" cy="13" r="6" />
              <path d="M9 13c0-1.5 1.5-2 3-2s3 .5 3 2-1.5 2-3 2-3-.5-3-2" />
              <circle cx="6" cy="6" r="1" fill="currentColor" />
              <circle cx="10" cy="6" r="1" fill="currentColor" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-mono font-semibold text-stone-50 tracking-tight">数据清洗</h2>
            <p className="text-sm text-stone-400 mt-1.5 leading-relaxed">
              使用 AI 清洗和标注采集的数据。选择 JSON 文件，配置筛选条件和标签，
              然后发送到清洗队列进行处理。
            </p>
          </div>
          {activeTasks.length > 0 && (
            <div className="ml-auto flex items-center gap-2 px-3 py-1.5 bg-[rgba(217,119,87,0.15)] border border-[rgba(217,119,87,0.25)] rounded-lg">
              <div className="w-2 h-2 bg-[#D97757] rounded-full animate-pulse" />
              <span className="text-sm font-mono text-[#E8A090]">
                {activeTasks.length} 个任务运行中
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Main two-column layout - right column determines height for left column */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Left Column - Scrape Results Panel (height synced with right column, scrolls if content overflows) */}
        <div
          className="overflow-hidden"
          style={rightPanelHeight ? { height: `${rightPanelHeight}px` } : { height: 'auto' }}
        >
          <ScrapeResultsPanel
            selectedFiles={selectedFiles}
            onSelectionChange={setSelectedFiles}
            onFilesLoaded={handleFilesLoaded}
            accounts={accounts}
          />
        </div>

        {/* Right Column - Washing Machine (natural height determines max height for left column) */}
        <div ref={rightPanelRef}>
          <WashingMachine
            selectedFiles={selectedFiles}
            onTaskSubmit={handleTaskSubmit}
            disabled={activeTasks.length >= 3} // Limit concurrent tasks
          />
        </div>
      </div>

      {/* Full-width sections below */}
      <div className="space-y-6 mt-6">
        {/* Processing Queue */}
        <ProcessingQueue
          tasks={tasks}
          onCancelTask={handleCancelTask}
          onDeleteTask={handleDeleteTask}
          backendTaskIds={backendTaskIdsRef.current}
        />

        {/* Cleaned Results - Always visible */}
        <CleanedResultsViewer
          files={cleanedFiles}
          onFileSelect={handleCleanedFileSelect}
          onFileDeleted={loadCleanedResults}
          selectedFileData={selectedCleanedData}
          loading={loadingCleanedData}
        />
      </div>

    </div>
  );
}
