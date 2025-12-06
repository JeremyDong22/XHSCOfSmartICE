// Results viewer component for displaying scrape output files
// Version: 3.0 - Added visual preview mode with Xiaohongshu-style card grid
// Changes: Toggle between JSON and visual preview, card grid with images/likes/author

'use client';

import { useState, useEffect } from 'react';
import { ResultFile, getScrapeResults, getScrapeResult, deleteScrapeResult, ScrapeResultData, XHSPost } from '@/lib/api';

interface ResultsViewerProps {
  refreshTrigger: number;
}

// Format like count (e.g., 12000 -> 1.2万)
function formatLikes(likes: number): string {
  if (likes >= 10000) {
    return `${(likes / 10000).toFixed(1)}万`;
  }
  return likes.toString();
}

// Post card component mimicking Xiaohongshu's style
function PostCard({ post }: { post: XHSPost }) {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Calculate aspect ratio for proper image sizing
  const aspectRatio = post.card_height / post.card_width;
  const displayHeight = Math.min(Math.max(aspectRatio * 100, 100), 180);

  return (
    <a
      href={post.tokenized_url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-stone-900 rounded-xl overflow-hidden border border-stone-700 hover:border-stone-500 transition-all hover:shadow-lg group"
    >
      {/* Cover Image Container */}
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
        {/* Title */}
        <h3 className="text-sm text-stone-100 font-medium line-clamp-2 mb-2 min-h-[2.5rem] group-hover:text-white transition-colors">
          {post.title || '无标题'}
        </h3>

        {/* Author and Likes Row */}
        <div className="flex items-center justify-between">
          {/* Author */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <div className="w-5 h-5 rounded-full bg-stone-700 overflow-hidden flex-shrink-0">
              <img
                src={post.author_avatar}
                alt={post.author}
                className="w-full h-full object-cover"
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
            </div>
            <span className="text-xs text-stone-400 truncate">{post.author}</span>
          </div>

          {/* Likes */}
          <div className="flex items-center gap-1 flex-shrink-0 ml-2">
            <svg className="w-3.5 h-3.5 text-red-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
            </svg>
            <span className="text-xs text-stone-400 font-medium">{formatLikes(post.likes)}</span>
          </div>
        </div>
      </div>
    </a>
  );
}

// Visual preview grid component
function VisualPreview({ data }: { data: ScrapeResultData }) {
  if (!data.posts || data.posts.length === 0) {
    return (
      <div className="text-center py-8 text-stone-500 text-sm">
        No posts in this result file.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header stats */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-stone-400">
          关键词: <span className="text-[#E8A090] font-medium">{data.keyword}</span>
        </span>
        <span className="text-stone-500">|</span>
        <span className="text-stone-400">
          共 <span className="text-stone-200 font-medium">{data.total_posts}</span> 条结果
        </span>
        <span className="text-stone-500">|</span>
        <span className="text-stone-400 text-xs">
          {new Date(data.scraped_at).toLocaleString('zh-CN')}
        </span>
      </div>

      {/* Masonry-style grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {data.posts.map((post) => (
          <PostCard key={post.note_id} post={post} />
        ))}
      </div>
    </div>
  );
}

export default function ResultsViewer({ refreshTrigger }: ResultsViewerProps) {
  const [files, setFiles] = useState<ResultFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<ScrapeResultData | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'visual' | 'json'>('visual');

  useEffect(() => {
    loadFiles();
  }, [refreshTrigger]);

  const loadFiles = async () => {
    try {
      const results = await getScrapeResults();
      setFiles(results);
    } catch (error) {
      console.error('Failed to load results:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileClick = async (filename: string) => {
    if (selectedFile === filename) {
      setSelectedFile(null);
      setFileContent(null);
      return;
    }

    setSelectedFile(filename);
    setContentLoading(true);

    try {
      const content = await getScrapeResult(filename) as ScrapeResultData;
      setFileContent(content);
    } catch (error) {
      console.error('Failed to load file:', error);
      alert('Failed to load file content');
    } finally {
      setContentLoading(false);
    }
  };

  const handleDelete = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();

    const confirmed = confirm(`Are you sure you want to delete ${filename}?\n\nThis action cannot be undone.`);
    if (!confirmed) return;

    try {
      await deleteScrapeResult(filename);

      if (selectedFile === filename) {
        setSelectedFile(null);
        setFileContent(null);
      }

      await loadFiles();
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert(error instanceof Error ? error.message : 'Failed to delete file');
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="bg-stone-800 rounded-xl p-6 border border-stone-700">
        <h2 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-4">
          Scrape Results
        </h2>
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-12 bg-stone-700 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-stone-800 rounded-xl p-6 border border-stone-700">
      <h2 className="text-xs font-mono font-medium text-stone-500 uppercase tracking-widest mb-4">
        Scrape Results
      </h2>

      {files.length === 0 ? (
        <div className="text-center py-8 text-stone-500 text-sm">
          <p>No results yet. Start a scraping task to see results here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {files.map((file) => (
            <div key={file.filename}>
              <div
                className={`flex items-stretch rounded-lg transition-all ${
                  selectedFile === file.filename
                    ? 'bg-[rgba(217,119,87,0.1)] border border-[rgba(217,119,87,0.25)]'
                    : 'bg-stone-900 border border-stone-700 hover:border-stone-600'
                }`}
              >
                <button
                  onClick={() => handleFileClick(file.filename)}
                  aria-expanded={selectedFile === file.filename}
                  className="flex-1 text-left px-4 py-3 rounded-l-lg transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-stone-50 truncate flex-1 text-sm">
                      {file.filename}
                    </span>
                    <span className="font-mono text-xs text-stone-500 ml-4">
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                </button>
                <button
                  onClick={(e) => handleDelete(file.filename, e)}
                  className="px-3 text-red-300 hover:bg-[rgba(239,68,68,0.2)] transition-colors rounded-r-lg"
                  title="Delete file"
                >
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
                </button>
              </div>

              {/* File content preview */}
              {selectedFile === file.filename && (
                <div className="mt-2 bg-black border border-stone-800 rounded-lg overflow-hidden">
                  {/* View mode toggle header */}
                  <div className="px-4 py-2 border-b border-stone-800 flex items-center justify-between">
                    <span className="font-mono text-xs text-stone-500 uppercase tracking-widest">
                      {viewMode === 'visual' ? 'Visual Preview' : 'JSON Preview'}
                    </span>
                    <div className="flex items-center gap-1 bg-stone-900 rounded-lg p-0.5">
                      <button
                        onClick={() => setViewMode('visual')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                          viewMode === 'visual'
                            ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090]'
                            : 'text-stone-400 hover:text-stone-300'
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="3" y="3" width="7" height="7" rx="1" />
                            <rect x="14" y="3" width="7" height="7" rx="1" />
                            <rect x="3" y="14" width="7" height="7" rx="1" />
                            <rect x="14" y="14" width="7" height="7" rx="1" />
                          </svg>
                          Cards
                        </span>
                      </button>
                      <button
                        onClick={() => setViewMode('json')}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                          viewMode === 'json'
                            ? 'bg-[rgba(217,119,87,0.2)] text-[#E8A090]'
                            : 'text-stone-400 hover:text-stone-300'
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" />
                          </svg>
                          JSON
                        </span>
                      </button>
                    </div>
                  </div>

                  {/* Content area */}
                  <div className="p-4 max-h-[600px] overflow-auto">
                    {contentLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <div className="animate-spin w-6 h-6 border-2 border-stone-600 border-t-[#D97757] rounded-full"></div>
                      </div>
                    ) : fileContent ? (
                      viewMode === 'visual' ? (
                        <VisualPreview data={fileContent} />
                      ) : (
                        <pre className="font-mono text-sm text-emerald-300 whitespace-pre-wrap">
                          {JSON.stringify(fileContent, null, 2)}
                        </pre>
                      )
                    ) : (
                      <p className="text-stone-600 font-mono text-sm">No content</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
