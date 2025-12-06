// Data Cleaning Tab - Main container for the "Data Laundry" feature
// Version: 2.3 - Removed debug console.log statements
// Changes: Cleaned up logging after debugging cleaned results viewer
// Previous: Added persistent task restore on page refresh

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
  CleaningRequest,
  CleanedResultFile as ApiCleanedResultFile,
  CleaningTaskFull,
  CleaningConfigStored,
} from '@/lib/api';

export default function DataCleaningTab() {
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
          labelCount: backendTask.config.labelBy.labelCount,
          labels: backendTask.config.labelBy.labels,
          prompt: backendTask.config.labelBy.prompt,
        },
        unifiedPrompt: backendTask.config.unifiedPrompt,
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

    // Build the cleaning request for the backend
    // Filter labels to only include entries with non-empty names
    const filteredLabels = task.config.labelBy.labels
      .filter(l => l.name.trim().length > 0)
      .map(l => ({
        name: l.name.trim(),
        description: l.description.trim(),
      }));

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
        labelCount: task.config.labelBy.labelCount,
        labels: task.config.labelBy.labels,
        prompt: task.config.labelBy.prompt,
      },
      unifiedPrompt: task.config.unifiedPrompt,
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
        categories: filteredLabels,  // Now sends array of {name, description} objects
        prompt: task.config.unifiedPrompt,  // Use the output format prompt
      } : null,
      // Add frontend task ID and config for persistent storage
      frontend_task_id: task.id,
      frontend_config: frontendConfig,
    };

    // Mark task as processing
    setTasks(prev => prev.map(t =>
      t.id === task.id
        ? { ...t, status: 'processing' as const, startedAt: new Date(), progress: 10 }
        : t
    ));

    try {
      // Call the backend API - returns immediately with task_id
      const response = await startCleaning(request);

      // Store the backend task_id mapping
      const backendTaskId = (response as unknown as { task_id: string }).task_id;
      backendTaskIdsRef.current.set(task.id, backendTaskId);

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

  // Handle task cancellation
  const handleCancelTask = useCallback((taskId: string) => {
    // Stop polling for this task
    const interval = pollingIntervalsRef.current.get(taskId);
    if (interval) {
      clearInterval(interval);
      pollingIntervalsRef.current.delete(taskId);
    }
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
                labelCount: data.metadata.label_by_condition.categories?.length || 0,
                prompt: data.metadata.label_by_condition.prompt,
                categories: data.metadata.label_by_condition.categories,  // Pass categories for filter dropdown
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
            <h2 className="text-lg font-mono font-semibold text-stone-50 tracking-tight">Data Laundry</h2>
            <p className="text-sm text-stone-400 mt-1.5 leading-relaxed">
              Clean and label your scraped data using AI. Select JSON files, configure filters and labels,
              then send them through the Spin Cycle for processing.
            </p>
          </div>
          {activeTasks.length > 0 && (
            <div className="ml-auto flex items-center gap-2 px-3 py-1.5 bg-[rgba(217,119,87,0.15)] border border-[rgba(217,119,87,0.25)] rounded-lg">
              <div className="w-2 h-2 bg-[#D97757] rounded-full animate-pulse" />
              <span className="text-sm font-mono text-[#E8A090]">
                {activeTasks.length} task{activeTasks.length > 1 ? 's' : ''} running
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Main two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column - Scrape Results Panel */}
        <div className="min-h-[600px]">
          <ScrapeResultsPanel
            selectedFiles={selectedFiles}
            onSelectionChange={setSelectedFiles}
            onFilesLoaded={handleFilesLoaded}
          />
        </div>

        {/* Right Column - Washing Machine */}
        <div>
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
