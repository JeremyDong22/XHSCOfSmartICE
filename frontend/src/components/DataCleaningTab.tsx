// Data Cleaning Tab - Main container for the "Data Laundry" feature
// Version: 1.4 - Updated to support new multi-target Label By configuration
// Layout: Two-column grid (ScrapeResultsPanel | WashingMachine), then full-width Queue and Results below

'use client';

import { useState, useCallback } from 'react';
import ScrapeResultsPanel, { EnrichedResultFile } from './ScrapeResultsPanel';
import WashingMachine, { CleaningTask } from './WashingMachine';
import ProcessingQueue from './ProcessingQueue';
import CleanedResultsViewer, { CleanedResultFile, CleanedResultData } from './CleanedResultsViewer';

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

  // Handle files loaded from scrape results panel
  const handleFilesLoaded = useCallback((files: EnrichedResultFile[]) => {
    setAvailableFiles(files);
  }, []);

  // Handle task submission from washing machine
  const handleTaskSubmit = useCallback((task: CleaningTask) => {
    // Add task to queue with queued status
    setTasks(prev => [...prev, task]);

    // Simulate task processing (in production, this would be an API call)
    simulateTaskProcessing(task.id);

    // Clear selection after submission
    setSelectedFiles([]);
  }, []);

  // Simulate task processing (placeholder for real backend integration)
  const simulateTaskProcessing = (taskId: string) => {
    // Start processing after a short delay
    setTimeout(() => {
      setTasks(prev => prev.map(t =>
        t.id === taskId
          ? { ...t, status: 'processing' as const, startedAt: new Date(), progress: 0 }
          : t
      ));

      // Simulate progress updates
      let progress = 0;
      const progressInterval = setInterval(() => {
        progress += Math.random() * 15 + 5;
        if (progress >= 100) {
          clearInterval(progressInterval);

          // Mark as completed
          setTasks(prev => prev.map(t =>
            t.id === taskId
              ? { ...t, status: 'completed' as const, progress: 100, completedAt: new Date() }
              : t
          ));

          // Add a mock cleaned result file
          const newCleanedFile: CleanedResultFile = {
            filename: `cleaned_${taskId}.json`,
            size: Math.floor(Math.random() * 500000) + 50000,
            cleanedAt: new Date(),
          };
          setCleanedFiles(prev => [newCleanedFile, ...prev]);
        } else {
          setTasks(prev => prev.map(t =>
            t.id === taskId
              ? { ...t, progress: Math.min(progress, 99) }
              : t
          ));
        }
      }, 800);
    }, 500);
  };

  // Handle task cancellation
  const handleCancelTask = useCallback((taskId: string) => {
    setTasks(prev => prev.filter(t => t.id !== taskId));
  }, []);

  // Handle cleaned file selection (mock data loader)
  const handleCleanedFileSelect = useCallback((filename: string) => {
    setLoadingCleanedData(true);

    // Find the task that created this file
    const task = tasks.find(t => `cleaned_${t.id}.json` === filename);

    // Simulate loading cleaned data
    setTimeout(() => {
      const mockData: CleanedResultData = {
        metadata: {
          cleanedAt: new Date().toISOString(),
          processedBy: 'gpt-4-vision-preview',
          processingTime: Math.floor(Math.random() * 300) + 30,
          filterByCondition: task?.config.filterBy.enabled
            ? {
                metric: task.config.filterBy.metric,
                operator: task.config.filterBy.operator,
                value: task.config.filterBy.value,
              }
            : undefined,
          labelByCondition: task?.config.labelBy.enabled
            ? {
                imageTarget: task.config.labelBy.imageTarget,
                textTarget: task.config.labelBy.textTarget,
                labelCount: task.config.labelBy.labelCount,
                prompt: task.config.labelBy.prompt,
              }
            : undefined,
          originalFiles: task?.files || [],
          totalPostsInput: 50,
          totalPostsOutput: 42,
        },
        posts: [], // In production, this would be populated with actual labeled posts
      };

      setSelectedCleanedData(mockData);
      setLoadingCleanedData(false);
    }, 500);
  }, [tasks]);

  // Count active tasks
  const activeTasks = tasks.filter(t => t.status === 'processing' || t.status === 'queued');

  return (
    <div className="space-y-6">
      {/* Header description */}
      <div className="bg-stone-800 rounded-xl border border-stone-700 p-4">
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
            <h2 className="text-lg font-semibold text-stone-100">Data Laundry</h2>
            <p className="text-sm text-stone-400 mt-1">
              Clean and label your scraped data using AI. Select JSON files, configure filters and labels,
              then send them through the Spin Cycle for processing.
            </p>
          </div>
          {activeTasks.length > 0 && (
            <div className="ml-auto flex items-center gap-2 px-3 py-1.5 bg-[rgba(217,119,87,0.15)] border border-[rgba(217,119,87,0.25)] rounded-lg">
              <div className="w-2 h-2 bg-[#D97757] rounded-full animate-pulse" />
              <span className="text-sm text-[#E8A090]">
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
          selectedFileData={selectedCleanedData}
          loading={loadingCleanedData}
        />
      </div>

    </div>
  );
}
