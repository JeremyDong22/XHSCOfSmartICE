// Scrape Results Panel - Left side of Data Laundry tab
// Version: 1.3 - Fixed loading flash by moving loading state inline
// Changes: Loading skeleton now renders inside the same container structure
// Previous: Removed "Configure washing" footer section

'use client';

import { useState, useEffect, useMemo } from 'react';
import { ResultFile, getScrapeResults, getScrapeResult, ScrapeResultData } from '@/lib/api';

// Extended result file with loaded metadata for filtering
export interface EnrichedResultFile extends ResultFile {
  keyword?: string;
  accountId?: number;
  scrapedAt?: Date;
  totalPosts?: number;
}

interface ScrapeResultsPanelProps {
  selectedFiles: string[];
  onSelectionChange: (files: string[]) => void;
  onFilesLoaded?: (files: EnrichedResultFile[]) => void;
}

type SortOrder = 'newest' | 'oldest';

export default function ScrapeResultsPanel({
  selectedFiles,
  onSelectionChange,
  onFilesLoaded,
}: ScrapeResultsPanelProps) {
  const [files, setFiles] = useState<EnrichedResultFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [keywordFilter, setKeywordFilter] = useState('');
  const [accountFilter, setAccountFilter] = useState<number | 'all'>('all');
  const [sortOrder, setSortOrder] = useState<SortOrder>('newest');
  const [loadingMetadata, setLoadingMetadata] = useState<Set<string>>(new Set());

  // Load file list and metadata on mount
  useEffect(() => {
    loadFilesWithMetadata();
  }, []);

  const loadFilesWithMetadata = async () => {
    try {
      setLoading(true);
      const results = await getScrapeResults();

      // Load metadata for each file to enable filtering
      const enrichedFiles: EnrichedResultFile[] = [];

      for (const file of results) {
        try {
          // Parse filename pattern: keyword_accountX_timestamp.json
          const match = file.filename.match(/^(.+)_account(\d+)_(\d+)\.json$/);

          if (match) {
            enrichedFiles.push({
              ...file,
              keyword: match[1],
              accountId: parseInt(match[2]),
              scrapedAt: new Date(parseInt(match[3])),
            });
          } else {
            enrichedFiles.push(file);
          }
        } catch {
          enrichedFiles.push(file);
        }
      }

      setFiles(enrichedFiles);
      onFilesLoaded?.(enrichedFiles);
    } catch (error) {
      console.error('Failed to load results:', error);
    } finally {
      setLoading(false);
    }
  };

  // Get unique accounts for filter dropdown
  const uniqueAccounts = useMemo(() => {
    const accounts = new Set<number>();
    files.forEach(f => f.accountId && accounts.add(f.accountId));
    return Array.from(accounts).sort((a, b) => a - b);
  }, [files]);

  // Get unique keywords for suggestions
  const uniqueKeywords = useMemo(() => {
    const keywords = new Set<string>();
    files.forEach(f => f.keyword && keywords.add(f.keyword));
    return Array.from(keywords);
  }, [files]);

  // Filter and sort files
  const filteredFiles = useMemo(() => {
    let result = [...files];

    // Filter by keyword
    if (keywordFilter.trim()) {
      const searchLower = keywordFilter.toLowerCase();
      result = result.filter(f =>
        f.keyword?.toLowerCase().includes(searchLower) ||
        f.filename.toLowerCase().includes(searchLower)
      );
    }

    // Filter by account
    if (accountFilter !== 'all') {
      result = result.filter(f => f.accountId === accountFilter);
    }

    // Sort by date
    result.sort((a, b) => {
      const dateA = a.scrapedAt?.getTime() || 0;
      const dateB = b.scrapedAt?.getTime() || 0;
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });

    return result;
  }, [files, keywordFilter, accountFilter, sortOrder]);

  // Toggle file selection
  const toggleFileSelection = (filename: string) => {
    if (selectedFiles.includes(filename)) {
      onSelectionChange(selectedFiles.filter(f => f !== filename));
    } else {
      onSelectionChange([...selectedFiles, filename]);
    }
  };

  // Select all visible files
  const selectAll = () => {
    const allFilenames = filteredFiles.map(f => f.filename);
    onSelectionChange(allFilenames);
  };

  // Deselect all
  const deselectAll = () => {
    onSelectionChange([]);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (date?: Date) => {
    if (!date) return '—';
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="bg-stone-800 rounded-xl border border-stone-700 h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-stone-700">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">1</span>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-stone-100">Select from Scrape Results</h3>
          </div>
          <span className="text-xs text-stone-500">
            {selectedFiles.length} / {filteredFiles.length} selected
          </span>
        </div>

        {/* Filters Row */}
        <div className="space-y-2">
          {/* Keyword Filter */}
          <div className="relative">
            <input
              type="text"
              value={keywordFilter}
              onChange={(e) => setKeywordFilter(e.target.value)}
              placeholder="Filter by keyword..."
              className="w-full px-3 py-2 bg-stone-900 border border-stone-700 rounded-lg text-sm text-stone-200 placeholder:text-stone-500 focus:border-[#D97757] focus:ring-1 focus:ring-[rgba(217,119,87,0.3)]"
            />
            {keywordFilter && (
              <button
                onClick={() => setKeywordFilter('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-500 hover:text-stone-300"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Account and Sort Row */}
          <div className="flex gap-2">
            {/* Account Filter */}
            <select
              value={accountFilter}
              onChange={(e) => setAccountFilter(e.target.value === 'all' ? 'all' : parseInt(e.target.value))}
              className="flex-1 px-3 py-2 bg-stone-900 border border-stone-700 rounded-lg text-sm text-stone-200"
            >
              <option value="all">All Accounts</option>
              {uniqueAccounts.map(id => (
                <option key={id} value={id}>Account {id}</option>
              ))}
            </select>

            {/* Sort Order */}
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              className="px-3 py-2 bg-stone-900 border border-stone-700 rounded-lg text-sm text-stone-200"
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
            </select>
          </div>
        </div>

        {/* Selection Controls */}
        <div className="flex gap-2 mt-3">
          <button
            onClick={selectAll}
            className="px-3 py-1.5 text-xs font-medium text-emerald-300 bg-[rgba(16,185,129,0.15)] border border-[rgba(16,185,129,0.25)] rounded-md hover:bg-[rgba(16,185,129,0.25)] transition-colors"
          >
            Select All
          </button>
          <button
            onClick={deselectAll}
            disabled={selectedFiles.length === 0}
            className="px-3 py-1.5 text-xs font-medium text-stone-400 bg-stone-900 border border-stone-700 rounded-md hover:bg-stone-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="space-y-1">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-stone-900 rounded-lg animate-pulse border border-stone-700" />
            ))}
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="text-center py-8 text-stone-500 text-sm">
            {files.length === 0
              ? 'No scrape results yet. Run a scrape task first.'
              : 'No files match your filters.'}
          </div>
        ) : (
          <div className="space-y-1">
            {filteredFiles.map((file) => (
              <label
                key={file.filename}
                className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                  selectedFiles.includes(file.filename)
                    ? 'bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.25)]'
                    : 'bg-stone-900 border border-stone-700 hover:border-stone-600'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedFiles.includes(file.filename)}
                  onChange={() => toggleFileSelection(file.filename)}
                  className="mt-0.5 flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  {/* Keyword Badge */}
                  {file.keyword && (
                    <span className="inline-block px-2 py-0.5 text-xs font-medium text-[#E8A090] bg-[rgba(217,119,87,0.15)] rounded mb-1">
                      {file.keyword}
                    </span>
                  )}

                  {/* Filename */}
                  <div className="text-sm text-stone-200 truncate">
                    {file.filename}
                  </div>

                  {/* Metadata Row */}
                  <div className="flex items-center gap-3 mt-1 text-xs text-stone-500">
                    {file.accountId && (
                      <span>Account {file.accountId}</span>
                    )}
                    <span>{formatFileSize(file.size)}</span>
                    <span>{formatDate(file.scrapedAt)}</span>
                  </div>
                </div>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
