// Results viewer component for displaying scrape output files
// Version: 2.0 - Anthropic-inspired dark theme with pure black JSON preview

'use client';

import { useState, useEffect } from 'react';
import { ResultFile, getScrapeResults, getScrapeResult, deleteScrapeResult } from '@/lib/api';

interface ResultsViewerProps {
  refreshTrigger: number;
}

export default function ResultsViewer({ refreshTrigger }: ResultsViewerProps) {
  const [files, setFiles] = useState<ResultFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<unknown>(null);
  const [contentLoading, setContentLoading] = useState(false);

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
      const content = await getScrapeResult(filename);
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
                <div className="mt-2 bg-black border border-stone-800 rounded-lg overflow-auto max-h-96">
                  <div className="px-4 py-2 border-b border-stone-800">
                    <span className="font-mono text-xs text-stone-500 uppercase tracking-widest">
                      JSON Preview
                    </span>
                  </div>
                  <div className="p-4">
                    {contentLoading ? (
                      <p className="text-stone-600 font-mono text-sm">Loading...</p>
                    ) : fileContent ? (
                      <pre className="font-mono text-sm text-emerald-300 whitespace-pre-wrap">
                        {JSON.stringify(fileContent, null, 2)}
                      </pre>
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