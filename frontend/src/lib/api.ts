// API client for XHS Multi-Account Scraper
// Version: 1.0 - REST API client functions

const API_BASE = 'http://localhost:8000/api';

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

export interface ScrapeRequest {
  account_id: number;
  keyword: string;
  max_posts: number;
  min_likes: number;
  min_collects: number;
  min_comments: number;
}

export interface ScrapeResponse {
  success: boolean;
  posts_count: number;
  filepath: string;
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
