// Cleaned Results Viewer - Displays processed/cleaned JSON files with metadata
// Version: 1.2 - Updated labelByCondition to support multi-target selection
// Features: Metadata display, group by label, filter by label value, sort by metrics

'use client';

import { useState, useMemo } from 'react';
import { XHSPost } from '@/lib/api';

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
  };
  originalFiles: string[];
  totalPostsInput: number;
  totalPostsOutput: number;
}

export interface LabeledPost extends XHSPost {
  labels?: {
    coverImageLabel?: string;
    imagesLabel?: string;
    titleLabel?: string;
    contentLabel?: string;
    confidence?: number;
    reasoning?: string;
  };
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
  selectedFileData?: CleanedResultData | null;
  loading?: boolean;
}

type SortField = 'likes' | 'collects' | 'comments';
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

// Post card component with label display
function LabeledPostCard({ post }: { post: LabeledPost }) {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  const aspectRatio = post.card_height / post.card_width;
  const displayHeight = Math.min(Math.max(aspectRatio * 100, 100), 180);

  // Get the primary label to display
  const primaryLabel = post.labels?.coverImageLabel ||
    post.labels?.contentLabel ||
    post.labels?.titleLabel ||
    post.labels?.imagesLabel;

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

        {/* Confidence badge if available */}
        {post.labels?.confidence !== undefined && (
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1 bg-stone-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full"
                style={{ width: `${post.labels.confidence * 100}%` }}
              />
            </div>
            <span className="text-xs text-stone-500">
              {Math.round(post.labels.confidence * 100)}%
            </span>
          </div>
        )}
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
  selectedFileData,
  loading = false,
}: CleanedResultsViewerProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('visual');
  const [sortField, setSortField] = useState<SortField>('likes');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [groupByLabel, setGroupByLabel] = useState(false);
  const [selectedLabelFilter, setSelectedLabelFilter] = useState<string>('all');

  // Handle file selection
  const handleFileClick = (filename: string) => {
    if (selectedFile === filename) {
      setSelectedFile(null);
    } else {
      setSelectedFile(filename);
      onFileSelect?.(filename);
    }
  };

  // Get unique labels from data
  const availableLabels = useMemo(() => {
    if (!selectedFileData?.posts) return [];
    const labels = new Set<string>();
    selectedFileData.posts.forEach(post => {
      const label = post.labels?.coverImageLabel ||
        post.labels?.contentLabel ||
        post.labels?.titleLabel ||
        post.labels?.imagesLabel;
      if (label) labels.add(label);
    });
    return Array.from(labels).sort();
  }, [selectedFileData]);

  // Filter and sort posts
  const processedPosts = useMemo(() => {
    if (!selectedFileData?.posts) return [];

    let result = [...selectedFileData.posts];

    // Filter by label
    if (selectedLabelFilter !== 'all') {
      result = result.filter(post => {
        const label = post.labels?.coverImageLabel ||
          post.labels?.contentLabel ||
          post.labels?.titleLabel ||
          post.labels?.imagesLabel;
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

  // Group posts by label
  const groupedPosts = useMemo(() => {
    if (!groupByLabel) return null;

    const groups: Record<string, LabeledPost[]> = {};
    processedPosts.forEach(post => {
      const label = post.labels?.coverImageLabel ||
        post.labels?.contentLabel ||
        post.labels?.titleLabel ||
        post.labels?.imagesLabel ||
        'Unlabeled';
      if (!groups[label]) groups[label] = [];
      groups[label].push(post);
    });
    return groups;
  }, [processedPosts, groupByLabel]);

  if (files.length === 0) {
    return (
      <div className="bg-stone-800 rounded-xl border border-stone-700 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">4</span>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-stone-100">Cleaning Results</h3>
          </div>
        </div>
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>No cleaned results yet. Process some files in the Washing Machine.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-stone-800 rounded-xl border border-stone-700">
      {/* Header */}
      <div className="p-4 border-b border-stone-700">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#D97757] to-[#B85C3E] flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">4</span>
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-stone-100">Cleaning Results</h3>
          </div>
        </div>

        {/* File list */}
        <div className="space-y-1 max-h-[200px] overflow-y-auto">
          {files.map((file) => (
            <button
              key={file.filename}
              onClick={() => handleFileClick(file.filename)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-all ${
                selectedFile === file.filename
                  ? 'bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.25)]'
                  : 'bg-stone-900 border border-stone-700 hover:border-stone-600'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-stone-200 truncate">{file.filename}</span>
                <span className="text-xs text-stone-500 ml-2">
                  {file.cleanedAt.toLocaleDateString('zh-CN')}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Content area */}
      {selectedFile && (
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-stone-600 border-t-[#D97757] rounded-full" />
            </div>
          ) : selectedFileData ? (
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
                  <select
                    value={sortField}
                    onChange={(e) => setSortField(e.target.value as SortField)}
                    className="px-3 py-1.5 bg-stone-900 border border-stone-700 rounded-lg text-xs text-stone-200"
                  >
                    <option value="likes">Sort by Likes</option>
                    <option value="collects">Sort by Collects</option>
                    <option value="comments">Sort by Comments</option>
                  </select>

                  <button
                    onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
                    className="p-1.5 bg-stone-900 border border-stone-700 rounded-lg hover:border-stone-600 transition-colors"
                    title={sortOrder === 'desc' ? 'Descending' : 'Ascending'}
                  >
                    <svg
                      className={`w-4 h-4 text-stone-400 transition-transform ${
                        sortOrder === 'asc' ? 'rotate-180' : ''
                      }`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>

                {/* Group by label toggle */}
                {availableLabels.length > 0 && (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={groupByLabel}
                      onChange={(e) => setGroupByLabel(e.target.checked)}
                    />
                    <span className="text-xs text-stone-400">Group by label</span>
                  </label>
                )}

                {/* Results count */}
                <span className="text-xs text-stone-500 ml-auto">
                  {processedPosts.length} posts
                </span>
              </div>

              {/* Posts display */}
              <div className="max-h-[600px] overflow-y-auto">
                {viewMode === 'visual' ? (
                  groupByLabel && groupedPosts ? (
                    <div className="space-y-6">
                      {Object.entries(groupedPosts).map(([label, posts]) => (
                        <div key={label}>
                          <div className="flex items-center gap-2 mb-3">
                            <span className="px-2 py-1 bg-[rgba(217,119,87,0.2)] text-[#E8A090] text-xs font-medium rounded">
                              {label}
                            </span>
                            <span className="text-xs text-stone-500">
                              {posts.length} posts
                            </span>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                            {posts.map((post) => (
                              <LabeledPostCard key={post.note_id} post={post} />
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                      {processedPosts.map((post) => (
                        <LabeledPostCard key={post.note_id} post={post} />
                      ))}
                    </div>
                  )
                ) : (
                  <pre className="font-mono text-sm text-emerald-300 whitespace-pre-wrap bg-black rounded-lg p-4">
                    {JSON.stringify(selectedFileData, null, 2)}
                  </pre>
                )}
              </div>
            </>
          ) : (
            <p className="text-stone-500 text-sm">No content available</p>
          )}
        </div>
      )}
    </div>
  );
}
