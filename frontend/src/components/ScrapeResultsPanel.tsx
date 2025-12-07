// Scrape Results Panel - Left side of Data Laundry tab
// Version: 1.9 - Added inline thumbnail preview for files
// Changes: Preview button shows small thumbnails in a single row
// Previous: v1.8 - Hide scrollbar for cleaner look

'use client';

import { useState, useEffect, useMemo } from 'react';
import { ResultFile, getScrapeResults, getScrapeResult, ScrapeResultData, Account } from '@/lib/api';

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
  accounts?: Account[];
}

type SortOrder = 'newest' | 'oldest';

export default function ScrapeResultsPanel({
  selectedFiles,
  onSelectionChange,
  onFilesLoaded,
  accounts = [],
}: ScrapeResultsPanelProps) {
  const [files, setFiles] = useState<EnrichedResultFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [keywordFilter, setKeywordFilter] = useState('');
  const [accountFilter, setAccountFilter] = useState<number | 'all'>('all');
  const [sortOrder, setSortOrder] = useState<SortOrder>('newest');
  const [loadingMetadata, setLoadingMetadata] = useState<Set<string>>(new Set());

  // Preview state: which file is being previewed and its thumbnail URLs
  const [previewFile, setPreviewFile] = useState<string | null>(null);
  const [previewThumbnails, setPreviewThumbnails] = useState<string[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Helper to get account display name (nickname or "Account X")
  const getAccountDisplayName = (accountId: number) => {
    const account = accounts.find(a => a.account_id === accountId);
    return account?.nickname || `Account ${accountId}`;
  };

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
          // Parse filename pattern: keyword_accountX_YYYYMMDD_HHMMSS.json
          const match = file.filename.match(/^(.+)_account(\d+)_(\d{8})_(\d{6})\.json$/);

          if (match) {
            // Parse YYYYMMDD_HHMMSS into Date
            const dateStr = match[3]; // YYYYMMDD
            const timeStr = match[4]; // HHMMSS
            const year = parseInt(dateStr.substring(0, 4));
            const month = parseInt(dateStr.substring(4, 6)) - 1; // 0-indexed
            const day = parseInt(dateStr.substring(6, 8));
            const hour = parseInt(timeStr.substring(0, 2));
            const minute = parseInt(timeStr.substring(2, 4));
            const second = parseInt(timeStr.substring(4, 6));

            enrichedFiles.push({
              ...file,
              keyword: match[1],
              accountId: parseInt(match[2]),
              scrapedAt: new Date(year, month, day, hour, minute, second),
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

  // Toggle preview for a file - load thumbnails from file data
  const togglePreview = async (filename: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // If already previewing this file, close it
    if (previewFile === filename) {
      setPreviewFile(null);
      setPreviewThumbnails([]);
      return;
    }

    // Load file data to get cover images
    setLoadingPreview(true);
    setPreviewFile(filename);

    try {
      const data = await getScrapeResult(filename);
      // Extract cover images from posts (show more to fill the row)
      const thumbnails = data.posts
        .slice(0, 30)
        .map(post => post.cover_image)
        .filter(Boolean);
      setPreviewThumbnails(thumbnails);
    } catch (error) {
      console.error('Failed to load preview:', error);
      setPreviewThumbnails([]);
    } finally {
      setLoadingPreview(false);
    }
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
            <h3 className="text-sm font-mono font-semibold text-stone-50 tracking-tight">选择采集结果</h3>
          </div>
          <span className="text-xs font-mono text-stone-500">
            已选 {selectedFiles.length} / {filteredFiles.length}
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
              placeholder="按关键词过滤..."
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
              <option value="all">全部账号</option>
              {uniqueAccounts.map(id => (
                <option key={id} value={id}>{getAccountDisplayName(id)}</option>
              ))}
            </select>

            {/* Sort Order */}
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as SortOrder)}
              className="px-3 py-2 bg-stone-900 border border-stone-700 rounded-lg text-sm text-stone-200"
            >
              <option value="newest">日期 ↓</option>
              <option value="oldest">日期 ↑</option>
            </select>
          </div>
        </div>

        {/* Selection Controls */}
        <div className="flex gap-2 mt-3">
          <button
            onClick={selectAll}
            className="px-3 py-1.5 text-xs font-medium text-emerald-300 bg-[rgba(16,185,129,0.15)] border border-[rgba(16,185,129,0.25)] rounded-md hover:bg-[rgba(16,185,129,0.25)] transition-colors"
          >
            全选
          </button>
          <button
            onClick={deselectAll}
            disabled={selectedFiles.length === 0}
            className="px-3 py-1.5 text-xs font-medium text-stone-400 bg-stone-900 border border-stone-700 rounded-md hover:bg-stone-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            清除
          </button>
        </div>
      </div>

      {/* File List - hide scrollbar but keep scrolling */}
      <div className="flex-1 overflow-y-auto p-2 scrollbar-hide">
        {loading ? (
          <div className="space-y-1">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-stone-900 rounded-lg animate-pulse border border-stone-700" />
            ))}
          </div>
        ) : filteredFiles.length === 0 ? (
          <div className="text-center py-8 text-stone-500 text-sm">
            {files.length === 0
              ? '暂无采集结果。请先运行采集任务。'
              : '没有符合筛选条件的文件。'}
          </div>
        ) : (
          <div className="space-y-1">
            {filteredFiles.map((file) => (
              <div
                key={file.filename}
                className={`rounded-lg transition-all ${
                  selectedFiles.includes(file.filename)
                    ? 'bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.25)]'
                    : 'bg-stone-900 border border-stone-700 hover:border-stone-600'
                }`}
              >
                {/* Main row with checkbox, info, and preview button */}
                <label className="flex items-start gap-3 p-3 cursor-pointer">
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
                    <div className="flex items-center gap-3 mt-1 text-xs font-mono text-stone-500">
                      {file.accountId && (
                        <span>{getAccountDisplayName(file.accountId)}</span>
                      )}
                      <span>{formatFileSize(file.size)}</span>
                      <span>{formatDate(file.scrapedAt)}</span>
                    </div>
                  </div>

                  {/* Preview button */}
                  <button
                    onClick={(e) => togglePreview(file.filename, e)}
                    className={`flex-shrink-0 px-2 py-1 text-xs rounded transition-all ${
                      previewFile === file.filename
                        ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090] border border-[rgba(217,119,87,0.3)]'
                        : 'bg-stone-800 text-stone-400 border border-stone-700 hover:border-stone-600 hover:text-stone-300'
                    }`}
                  >
                    {loadingPreview && previewFile === file.filename ? (
                      <span className="inline-block w-3 h-3 border border-stone-500 border-t-transparent rounded-full animate-spin" />
                    ) : previewFile === file.filename ? (
                      '收起'
                    ) : (
                      '预览'
                    )}
                  </button>
                </label>

                {/* Thumbnail preview row - aligned with keyword badge, extends to preview button */}
                {previewFile === file.filename && !loadingPreview && previewThumbnails.length > 0 && (
                  <div className="pb-2 pr-3 pl-[38px]">
                    <div className="flex gap-0.5 overflow-hidden">
                      {previewThumbnails.map((url, idx) => (
                        <div
                          key={idx}
                          className="w-8 h-8 flex-shrink-0 rounded-sm bg-stone-800 overflow-hidden"
                        >
                          <img
                            src={url}
                            alt=""
                            className="w-full h-full object-cover"
                            loading="lazy"
                            referrerPolicy="no-referrer"
                            onError={(e) => { e.currentTarget.style.display = 'none'; }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
