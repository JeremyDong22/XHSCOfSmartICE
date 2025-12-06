// Cleaned Results Viewer - Displays processed/cleaned JSON files with metadata
// Version: 2.0 - Preview now displays inline below selected file, increased list height
// Changes: Restructured layout so preview expands under the selected file row
// Previous: Fixed label filter dropdown key error with category objects

'use client';

import { useState, useMemo } from 'react';
import { XHSPost, deleteCleanedResult } from '@/lib/api';

// Types for cleaned data structure
export interface CleaningMetadata {
  cleanedAt: string;
  processedBy: string;  // Model name
  processingTime: number;  // In seconds
  filterByCondition?: {
    metric: string;
    operator: string;
    value: number;
  };
  labelByCondition?: {
    imageTarget: string | null;
    textTarget: string | null;
    labelCount: number;
    prompt: string;
    categories?: string[];  // User-defined categories for filter dropdown
  };
  originalFiles: string[];
  totalPostsInput: number;
  totalPostsOutput: number;
}

export interface LabeledPost extends XHSPost {
  // Labels from backend: { label: "category_name" } - simple structure from Gemini
  labels?: {
    label?: string;  // Main label assigned by Gemini
  };
  // Separate fields for confidence and reasoning (at post level, not nested)
  label_confidence?: number;
  label_reasoning?: string;
}

export interface CleanedResultData {
  metadata: CleaningMetadata;
  posts: LabeledPost[];
}

export interface CleanedResultFile {
  filename: string;
  size: number;
  cleanedAt: Date;
}

interface CleanedResultsViewerProps {
  files: CleanedResultFile[];
  onFileSelect?: (filename: string) => void;
  onFileDeleted?: () => void;  // Callback to refresh file list after deletion
  selectedFileData?: CleanedResultData | null;
  loading?: boolean;
}

type SortField = 'likes';
type SortOrder = 'asc' | 'desc';
type ViewMode = 'visual' | 'json';

// Format like count (e.g., 12000 -> 1.2万)
function formatLikes(likes: number): string {
  if (likes >= 10000) {
    return `${(likes / 10000).toFixed(1)}万`;
  }
  return likes.toString();
}

// Format date
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Format duration
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

// Format file size (matching ResultsViewer)
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Post card component with label display
function LabeledPostCard({ post }: { post: LabeledPost }) {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  const aspectRatio = post.card_height / post.card_width;
  const displayHeight = Math.min(Math.max(aspectRatio * 100, 100), 180);

  // Get the primary label to display (now using simple structure from backend)
  const primaryLabel = post.labels?.label;

  return (
    <a
      href={post.tokenized_url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-stone-900 rounded-xl overflow-hidden border border-stone-700 hover:border-stone-500 transition-all hover:shadow-lg group"
    >
      {/* Cover Image */}
      <div
        className="relative bg-stone-800 overflow-hidden"
        style={{ paddingBottom: `${displayHeight}%` }}
      >
        {!imageError ? (
          <>
            {!imageLoaded && (
              <div className="absolute inset-0 animate-pulse bg-stone-700" />
            )}
            <img
              src={post.cover_image}
              alt={post.title || 'Post cover'}
              className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
                imageLoaded ? 'opacity-100' : 'opacity-0'
              }`}
              loading="lazy"
              referrerPolicy="no-referrer"
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageError(true)}
            />
          </>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-stone-800">
            <svg className="w-8 h-8 text-stone-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}

        {/* Label badge */}
        {primaryLabel && (
          <div className="absolute top-2 left-2 px-2 py-1 bg-[rgba(217,119,87,0.9)] rounded-full">
            <span className="text-xs text-white font-medium">{primaryLabel}</span>
          </div>
        )}

        {/* Video indicator */}
        {post.is_video && (
          <div className="absolute top-2 right-2 bg-black/60 rounded-full px-2 py-1 flex items-center gap-1">
            <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
            <span className="text-xs text-white font-medium">视频</span>
          </div>
        )}
      </div>

      {/* Post Info */}
      <div className="p-3">
        <h3 className="text-sm text-stone-100 font-medium line-clamp-2 mb-2 min-h-[2.5rem] group-hover:text-white transition-colors">
          {post.title || '无标题'}
        </h3>

        {/* Author and Stats Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <div className="w-5 h-5 rounded-full bg-stone-700 overflow-hidden flex-shrink-0">
              <img
                src={post.author_avatar}
                alt={post.author}
                className="w-full h-full object-cover"
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
            </div>
            <span className="text-xs text-stone-400 truncate">{post.author}</span>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0 ml-2">
            <div className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5 text-red-400" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
              </svg>
              <span className="text-xs text-stone-400">{formatLikes(post.likes)}</span>
            </div>
          </div>
        </div>

      </div>
    </a>
  );
}

// Metadata display component
function MetadataSection({ metadata }: { metadata: CleaningMetadata }) {
  return (
    <div className="bg-stone-900 rounded-lg border border-stone-700 p-4 mb-4">
      <h4 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-3">
        Cleaning Metadata
      </h4>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        {/* Cleaned at */}
        <div>
          <p className="text-stone-500 text-xs">Cleaned At</p>
          <p className="text-stone-200">{formatDate(metadata.cleanedAt)}</p>
        </div>

        {/* Model */}
        <div>
          <p className="text-stone-500 text-xs">Model</p>
          <p className="text-[#E8A090] font-mono">{metadata.processedBy}</p>
        </div>

        {/* Processing time */}
        <div>
          <p className="text-stone-500 text-xs">Processing Time</p>
          <p className="text-stone-200">{formatDuration(metadata.processingTime)}</p>
        </div>

        {/* Posts count */}
        <div>
          <p className="text-stone-500 text-xs">Posts</p>
          <p className="text-stone-200">
            <span className="text-emerald-400">{metadata.totalPostsOutput}</span>
            <span className="text-stone-500"> / {metadata.totalPostsInput}</span>
          </p>
        </div>
      </div>

      {/* Conditions */}
      <div className="mt-4 pt-4 border-t border-stone-700 space-y-2">
        {metadata.filterByCondition && (
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-[rgba(59,130,246,0.2)] text-blue-300 text-xs rounded">
              Filter By
            </span>
            <span className="text-xs text-stone-300">
              {metadata.filterByCondition.metric} {metadata.filterByCondition.operator} {metadata.filterByCondition.value}
            </span>
          </div>
        )}

        {metadata.labelByCondition && (
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 bg-[rgba(217,119,87,0.2)] text-[#E8A090] text-xs rounded">
              Label By
            </span>
            <span className="text-xs text-stone-300">
              {[
                metadata.labelByCondition.imageTarget === 'cover_image' ? 'Cover Image' :
                metadata.labelByCondition.imageTarget === 'images' ? 'All Images' : null,
                metadata.labelByCondition.textTarget === 'title' ? 'Title Only' :
                metadata.labelByCondition.textTarget === 'content' ? 'Title + Content' : null,
              ].filter(Boolean).join(' + ')} ({metadata.labelByCondition.labelCount} labels)
            </span>
          </div>
        )}
      </div>

      {/* Original files */}
      <div className="mt-3">
        <p className="text-xs text-stone-500 mb-1">Source files:</p>
        <div className="flex flex-wrap gap-1">
          {metadata.originalFiles.slice(0, 5).map((file, i) => (
            <span key={i} className="px-1.5 py-0.5 bg-stone-800 rounded text-xs text-stone-400 truncate max-w-[150px]">
              {file}
            </span>
          ))}
          {metadata.originalFiles.length > 5 && (
            <span className="text-xs text-stone-500">+{metadata.originalFiles.length - 5} more</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CleanedResultsViewer({
  files,
  onFileSelect,
  onFileDeleted,
  selectedFileData,
  loading = false,
}: CleanedResultsViewerProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('visual');
  const [sortField, setSortField] = useState<SortField>('likes');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>('all');
  const [deleting, setDeleting] = useState<string | null>(null);

  // Sort files by cleanedAt date (newest first)
  const sortedFiles = useMemo(() => {
    return [...files].sort((a, b) => b.cleanedAt.getTime() - a.cleanedAt.getTime());
  }, [files]);

  // Handle file selection - toggle expand/collapse
  const handleFileClick = (filename: string) => {
    if (selectedFile === filename) {
      setSelectedFile(null);
    } else {
      setSelectedFile(filename);
      onFileSelect?.(filename);
    }
  };

  // Handle file deletion
  const handleDelete = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();  // Prevent file selection

    const confirmed = confirm(`Are you sure you want to delete "${filename}"?\n\nThis action cannot be undone.`);
    if (!confirmed) return;

    try {
      setDeleting(filename);
      await deleteCleanedResult(filename);

      // Clear selection if deleted file was selected
      if (selectedFile === filename) {
        setSelectedFile(null);
      }

      // Notify parent to refresh file list
      onFileDeleted?.();
    } catch (error) {
      console.error('Failed to delete cleaned result:', error);
      alert(error instanceof Error ? error.message : 'Failed to delete file');
    } finally {
      setDeleting(null);
    }
  };

  // Get categories from metadata (user-defined during labeling)
  // Falls back to extracting unique labels from posts if metadata doesn't have categories
  // Returns array of string names for use in filter dropdown
  const availableLabels = useMemo(() => {
    if (!selectedFileData) return [];

    // Prefer categories from metadata - extract just the name strings
    const categories = selectedFileData.metadata?.labelByCondition?.categories;
    if (categories?.length) {
      return categories.map((cat: { name: string; description: string } | string) =>
        typeof cat === 'string' ? cat : cat.name
      );
    }

    // Fallback: extract unique labels from posts
    if (!selectedFileData.posts) return [];
    const labels = new Set<string>();
    selectedFileData.posts.forEach(post => {
      const label = post.labels?.label;
      if (label) labels.add(label);
    });
    return Array.from(labels).sort();
  }, [selectedFileData]);

  // Filter and sort posts
  const processedPosts = useMemo(() => {
    if (!selectedFileData?.posts) return [];

    let result = [...selectedFileData.posts];

    // Filter by label (using the simple label structure from backend)
    if (selectedLabelFilter !== 'all') {
      result = result.filter(post => {
        const label = post.labels?.label;
        return label === selectedLabelFilter;
      });
    }

    // Sort
    result.sort((a, b) => {
      const aVal = a[sortField] || 0;
      const bVal = b[sortField] || 0;
      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });

    return result;
  }, [selectedFileData, selectedLabelFilter, sortField, sortOrder]);

  if (files.length === 0) {
    return (
      <div className="bg-stone-800 rounded-xl border border-stone-700 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">4</span>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-mono font-semibold text-stone-50 tracking-tight">Cleaning Results</h3>
          </div>
        </div>
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>No cleaned results yet. Process some files in the Washing Machine.</p>
        </div>
      </div>
    );
  }

  // Render inline preview content for a selected file
  const renderPreviewContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin w-6 h-6 border-2 border-stone-600 border-t-[#D97757] rounded-full" />
        </div>
      );
    }

    if (!selectedFileData) {
      return <p className="text-stone-500 text-sm py-4">No content available</p>;
    }

    return (
      <>
        {/* Metadata */}
        <MetadataSection metadata={selectedFileData.metadata} />

        {/* Controls row */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {/* View mode toggle */}
          <div className="flex items-center gap-1 bg-stone-900 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('visual')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                viewMode === 'visual'
                  ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090]'
                  : 'text-stone-400 hover:text-stone-300'
              }`}
            >
              Cards
            </button>
            <button
              onClick={() => setViewMode('json')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                viewMode === 'json'
                  ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090]'
                  : 'text-stone-400 hover:text-stone-300'
              }`}
            >
              JSON
            </button>
          </div>

          {/* Label filter */}
          {availableLabels.length > 0 && (
            <select
              value={selectedLabelFilter}
              onChange={(e) => setSelectedLabelFilter(e.target.value)}
              className="px-3 py-1.5 bg-stone-900 border border-stone-700 rounded-lg text-xs text-stone-200"
            >
              <option value="all">All Labels</option>
              {availableLabels.map(label => (
                <option key={label} value={label}>{label}</option>
              ))}
            </select>
          )}

          {/* Sort controls */}
          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 bg-stone-900 border border-stone-700 rounded-lg text-xs text-stone-200">
              Sort by Likes
            </span>

            <button
              type="button"
              onClick={() => {
                const newOrder = sortOrder === 'desc' ? 'asc' : 'desc';
                setSortOrder(newOrder);
              }}
              className={`px-2 py-1.5 bg-stone-900 border rounded-lg transition-all cursor-pointer select-none ${
                sortOrder === 'asc'
                  ? 'border-[rgba(217,119,87,0.5)] text-[#E8A090]'
                  : 'border-stone-700 text-stone-400 hover:border-stone-600'
              }`}
              title={sortOrder === 'desc' ? 'Click for Ascending' : 'Click for Descending'}
            >
              <div className="flex items-center gap-1">
                <svg
                  className={`w-4 h-4 transition-transform duration-200 ${
                    sortOrder === 'asc' ? 'rotate-180' : ''
                  }`}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M19 9l-7 7-7-7" />
                </svg>
                <span className="text-xs font-medium">
                  {sortOrder === 'desc' ? 'DESC' : 'ASC'}
                </span>
              </div>
            </button>
          </div>

          {/* Results count */}
          <span className="text-xs text-stone-500 ml-auto">
            {processedPosts.length} posts
          </span>
        </div>

        {/* Posts display */}
        <div className="max-h-[500px] overflow-y-auto">
          {viewMode === 'visual' ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {processedPosts.map((post) => (
                <LabeledPostCard key={post.note_id} post={post} />
              ))}
            </div>
          ) : (
            <pre className="font-mono text-sm text-emerald-300 whitespace-pre-wrap bg-black rounded-lg p-4 max-h-[400px] overflow-y-auto">
              {JSON.stringify(selectedFileData, null, 2)}
            </pre>
          )}
        </div>
      </>
    );
  };

  return (
    <div className="bg-stone-800 rounded-xl border border-stone-700">
      {/* Header */}
      <div className="p-4 border-b border-stone-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">4</span>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-mono font-semibold text-stone-50 tracking-tight">Cleaning Results</h3>
          </div>
          <span className="text-xs text-stone-500">{files.length} files</span>
        </div>
      </div>

      {/* File list with inline previews - increased max height */}
      <div className="p-4 space-y-2 max-h-[800px] overflow-y-auto">
        {sortedFiles.map((file) => (
          <div key={file.filename} className="space-y-0">
            {/* File row */}
            <div
              className={`flex items-stretch rounded-lg transition-all ${
                selectedFile === file.filename
                  ? 'bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.25)] rounded-b-none border-b-0'
                  : 'bg-stone-900 border border-stone-700 hover:border-stone-600'
              }`}
            >
              <button
                onClick={() => handleFileClick(file.filename)}
                className="flex-1 text-left px-4 py-3 rounded-l-lg transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {/* Expand/collapse indicator */}
                    <svg
                      className={`w-4 h-4 text-stone-400 transition-transform duration-200 ${
                        selectedFile === file.filename ? 'rotate-90' : ''
                      }`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M9 5l7 7-7 7" />
                    </svg>
                    <span className="font-medium text-stone-50 truncate text-sm">{file.filename}</span>
                  </div>
                  <span className="font-mono text-xs text-stone-500 ml-4">
                    {formatFileSize(file.size)}
                  </span>
                </div>
              </button>
              {/* Delete button */}
              <button
                onClick={(e) => handleDelete(file.filename, e)}
                disabled={deleting === file.filename}
                className="px-3 text-red-300 hover:bg-[rgba(239,68,68,0.2)] transition-colors rounded-r-lg disabled:opacity-50"
                title="Delete file"
              >
                {deleting === file.filename ? (
                  <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                ) : (
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
                )}
              </button>
            </div>

            {/* Inline preview - shows directly below selected file */}
            {selectedFile === file.filename && (
              <div className="bg-[rgba(217,119,87,0.05)] border border-[rgba(217,119,87,0.25)] border-t-0 rounded-b-lg p-4">
                {renderPreviewContent()}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
