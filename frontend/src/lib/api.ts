// API client for XHS Multi-Account Scraper
// Version: 2.2 - Added cancel cleaning task API
// Changes:
// - Added cancelCleaningTask function to stop running cleaning tasks
// Previous: Food industry refactor with binary classification and style labels

// Dynamically determine API base URL based on current hostname
const getApiBase = () => {
  if (typeof window === 'undefined') return 'http://localhost:8000/api';
  const hostname = window.location.hostname;
  return `http://${hostname}:8000/api`;
};

const API_BASE = getApiBase();

// XHS Post data structure from scrape results
export interface XHSPost {
  note_id: string;
  permanent_url: string;
  tokenized_url: string;
  title: string;
  author: string;
  author_avatar: string;
  author_profile_url: string;
  likes: number;
  cover_image: string;
  publish_date: string;
  card_width: number;
  card_height: number;
  is_video: boolean;
  scraped_at: string;
  content: string;
  images: string[];
  hashtags: string[];
  collects: number;
  comments: number;
}

// Scrape result JSON structure
export interface ScrapeResultData {
  keyword: string;
  account_id: number;
  scraped_at: string;
  scrape_mode: string;
  total_posts: number;
  posts: XHSPost[];
}

// Types
export interface Account {
  account_id: number;
  active: boolean;
  nickname: string;
  created_at: string;
  last_used: string | null;
  has_session: boolean;
  browser_open: boolean;
}

export interface Stats {
  total: number;
  active: number;
  inactive: number;
  with_session: number;
  browsers_open: number;
}

// Account usage statistics
export interface AccountStats {
  account_id: number;
  nickname?: string;
  is_active: boolean;
  created_at?: string;
  last_used_at?: string;
  lifetime: {
    total_scrapes: number;
    total_posts_scraped: number;
    total_browser_opens: number;
    total_browser_duration_seconds: number;
  };
  today: {
    scrape_count: number;
    posts_scraped: number;
    browser_opens: number;
    browser_duration_seconds: number;
  };
  this_hour: {
    scrape_count: number;
    posts_scraped: number;
    browser_opens: number;
    browser_duration_seconds: number;
  };
}

export interface ScrapeRequest {
  account_id: number;
  keyword: string;
  max_posts: number;
  min_likes: number;
  min_collects: number;
  min_comments: number;
  skip_videos: boolean;
}

export interface ScrapeResponse {
  success: boolean;
  posts_count: number;
  filepath: string;
}

export interface ScrapeStartResponse {
  success: boolean;
  task_id: string;
  message: string;
}

export interface ResultFile {
  filename: string;
  size: number;
}

// Account API
export async function getAccounts(activeOnly = false): Promise<Account[]> {
  const url = `${API_BASE}/accounts${activeOnly ? '?active_only=true' : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch accounts');
  return res.json();
}

export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/accounts/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

export async function createAccount(nickname = ''): Promise<Account> {
  const res = await fetch(`${API_BASE}/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname }),
  });
  if (!res.ok) throw new Error('Failed to create account');
  return res.json();
}

export async function updateAccount(accountId: number, data: { nickname?: string; active?: boolean }): Promise<void> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update account');
}

export async function deleteAccount(accountId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete account');
}

export async function activateAccount(accountId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}/activate`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to activate account');
}

export async function deactivateAccount(accountId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}/deactivate`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to deactivate account');
}

// Browser API
export async function getOpenBrowsers(): Promise<number[]> {
  const res = await fetch(`${API_BASE}/browsers`);
  if (!res.ok) throw new Error('Failed to fetch browsers');
  const data = await res.json();
  return data.browsers;
}

export async function openBrowser(accountId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/browsers/${accountId}/open`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to open browser');
}

export async function openBrowserForLogin(): Promise<number> {
  const res = await fetch(`${API_BASE}/browsers/login`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to open login browser');
  const data = await res.json();
  return data.account_id;
}

export async function closeBrowser(accountId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/browsers/${accountId}/close`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to close browser');
}

export async function closeAllBrowsers(): Promise<void> {
  const res = await fetch(`${API_BASE}/browsers/close-all`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to close all browsers');
}

export async function openAllBrowsers(): Promise<number[]> {
  const res = await fetch(`${API_BASE}/browsers/open-all`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to open all browsers');
  const data = await res.json();
  return data.browsers;
}

// Scraping API
export async function startScrape(request: ScrapeRequest): Promise<ScrapeResponse> {
  const res = await fetch(`${API_BASE}/scrape/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to start scrape');
  }
  return res.json();
}

export async function startScrapeAsync(request: ScrapeRequest): Promise<ScrapeStartResponse> {
  const res = await fetch(`${API_BASE}/scrape/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to start scrape');
  }
  return res.json();
}

export async function cancelScrape(taskId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/scrape/cancel/${taskId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to cancel scrape');
  }
}

export async function getScrapeResults(): Promise<ResultFile[]> {
  const res = await fetch(`${API_BASE}/scrape/results`);
  if (!res.ok) throw new Error('Failed to fetch results');
  return res.json();
}

export async function getScrapeResult(filename: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/scrape/results/${filename}`);
  if (!res.ok) throw new Error('Failed to fetch result');
  return res.json();
}

export async function deleteScrapeResult(filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}/scrape/results/${filename}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to delete result');
  }
}

// Account Stats API
export async function getAccountStats(accountId: number): Promise<AccountStats> {
  const res = await fetch(`${API_BASE}/accounts/${accountId}/stats`);
  if (!res.ok) throw new Error('Failed to fetch account stats');
  return res.json();
}

export async function getAllAccountsStats(): Promise<AccountStats[]> {
  const res = await fetch(`${API_BASE}/stats/all`);
  if (!res.ok) throw new Error('Failed to fetch all account stats');
  return res.json();
}

// Data Cleaning API Types
export interface FilterByRequest {
  metric: 'likes' | 'collects' | 'comments';
  operator: 'gte' | 'lte' | 'gt' | 'lt' | 'eq';
  value: number;
}

export interface LabelByRequest {
  image_target?: 'cover_image' | 'images' | null;
  text_target?: 'title' | 'content' | null;
  user_description: string;  // User's description of what posts they want to filter
  full_prompt: string;  // Complete prompt sent to Gemini (for transparency)
}

export interface CleaningRequest {
  source_files: string[];
  filter_by?: FilterByRequest | null;
  label_by?: LabelByRequest | null;
  output_filename?: string;
  // Frontend task tracking fields for persistent storage
  frontend_task_id?: string;
  frontend_config?: CleaningConfigStored;
}

export interface CleaningStartResponse {
  success: boolean;
  output_file: string;
  posts_processed: number;
  message: string;
}

export interface CleanedResultFile {
  filename: string;
  size: number;
  cleaned_at: string;
  total_posts: number;
}

export interface CleanedResultMetadata {
  cleaned_at: string;
  processed_by: string;
  processing_time_seconds: number;
  filter_by_condition?: {
    metric: string;
    operator: string;
    value: number;
  };
  label_by_condition?: {
    image_target: string | null;
    text_target: string | null;
    user_description: string;
    full_prompt: string;
  };
  original_files: string[];
  total_posts_input: number;
  total_posts_output: number;
}

export interface CleanedPost extends XHSPost {
  label?: string;  // Binary: "是" or "不是"
  style_label?: string;  // One of: "特写图", "环境图", "拼接图", "信息图"
  label_reasoning?: string;  // Explanation in Chinese
}

export interface CleanedResultData {
  metadata: CleanedResultMetadata;
  posts: CleanedPost[];
}

// Cleaning task status for polling background task progress
export interface CleaningTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  output_filename?: string;  // Set when completed
  error?: string;  // Set when failed
}

// Data Cleaning API Functions
export async function startCleaning(request: CleaningRequest): Promise<CleaningStartResponse> {
  const res = await fetch(`${API_BASE}/cleaning/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to start cleaning');
  }
  return res.json();
}

export async function getCleaningTaskStatus(taskId: string): Promise<CleaningTaskStatus> {
  const res = await fetch(`${API_BASE}/cleaning/tasks/${taskId}/status`);
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to fetch task status');
  }
  return res.json();
}

export async function getCleanedResults(): Promise<CleanedResultFile[]> {
  const res = await fetch(`${API_BASE}/cleaning/results`);
  if (!res.ok) throw new Error('Failed to fetch cleaned results');
  return res.json();
}

export async function getCleanedResult(filename: string): Promise<CleanedResultData> {
  const res = await fetch(`${API_BASE}/cleaning/results/${filename}`);
  if (!res.ok) throw new Error('Failed to fetch cleaned result');
  return res.json();
}

export async function deleteCleanedResult(filename: string): Promise<void> {
  const res = await fetch(`${API_BASE}/cleaning/results/${filename}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to delete cleaned result');
  }
}

// Types for persistent task storage (matching backend models)
export interface FilterByConfigStored {
  enabled: boolean;
  metric: string;
  operator: string;
  value: number;
}

export interface LabelByConfigStored {
  enabled: boolean;
  imageTarget: string | null;
  textTarget: string | null;
  userDescription: string;
  fullPrompt: string;
}

export interface CleaningConfigStored {
  filterBy: FilterByConfigStored;
  labelBy: LabelByConfigStored;
}

export interface CleaningTaskFull {
  id: string;  // Frontend task ID (e.g., task_1733556789)
  backend_task_id: string;  // Backend task ID (UUID)
  files: string[];  // Source filenames
  config: CleaningConfigStored;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  progress: number;
  error?: string;
  created_at: string;
}

// Get all cleaning tasks (for page refresh restore)
export async function getCleaningTasks(): Promise<CleaningTaskFull[]> {
  const res = await fetch(`${API_BASE}/cleaning/tasks`);
  if (!res.ok) throw new Error('Failed to fetch cleaning tasks');
  return res.json();
}

// Delete a cleaning task from persistent storage
export async function deleteCleaningTask(taskId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/cleaning/tasks/${taskId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to delete cleaning task');
  }
}

// Cancel a running cleaning task
export async function cancelCleaningTask(backendTaskId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/cleaning/tasks/${backendTaskId}/cancel`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to cancel cleaning task');
  }
}

// Cleaning log message from SSE
export interface CleaningLogMessage {
  type: 'connected' | 'log' | 'status';
  message?: string;
  task_id?: string;
  status?: string;
}

// Subscribe to cleaning task logs via SSE
// Returns a cleanup function to close the connection
export function subscribeToCleaningLogs(
  taskId: string,
  onLog: (message: string) => void,
  onStatus?: (status: string) => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/cleaning/logs/${taskId}`);

  eventSource.onmessage = (event) => {
    try {
      const data: CleaningLogMessage = JSON.parse(event.data);

      if (data.type === 'log' && data.message) {
        onLog(data.message);
      } else if (data.type === 'status' && data.status && onStatus) {
        onStatus(data.status);
      }
    } catch {
      // Ignore parse errors
    }
  };

  eventSource.onerror = () => {
    if (onError) {
      onError(new Error('SSE connection error'));
    }
    eventSource.close();
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
}
