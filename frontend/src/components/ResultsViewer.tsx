// Results viewer component for displaying scrape output files
// Version: 1.0 - Lists and displays scrape result JSON files

'use client';

import { useState, useEffect } from 'react';
import { ResultFile, getScrapeResults, getScrapeResult } from '@/lib/api';

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

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-sm">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Scrape Results</h2>
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Scrape Results</h2>

      {files.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No results yet. Start a scraping task to see results here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {files.map((file) => (
            <div key={file.filename}>
              <button
                onClick={() => handleFileClick(file.filename)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${
                  selectedFile === file.filename
                    ? 'bg-pink-50 border border-pink-200'
                    : 'bg-gray-50 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900 truncate flex-1">
                    {file.filename}
                  </span>
                  <span className="text-sm text-gray-500 ml-4">
                    {formatFileSize(file.size)}
                  </span>
                </div>
              </button>

              {/* File content preview */}
              {selectedFile === file.filename && (
                <div className="mt-2 p-4 bg-gray-900 rounded-lg overflow-auto max-h-96">
                  {contentLoading ? (
                    <p className="text-gray-400">Loading...</p>
                  ) : fileContent ? (
                    <pre className="text-sm text-green-400 whitespace-pre-wrap">
                      {JSON.stringify(fileContent, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-gray-400">No content</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
