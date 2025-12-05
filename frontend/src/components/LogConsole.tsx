// Log console component for displaying real-time scrape progress
// Version: 2.1 - Fixed SSE URL path and data format to match backend API
// Changed: URL now points to backend port 8000, corrected path order

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface LogConsoleProps {
  taskId: string;
  onComplete: (status: string) => void;
}

interface LogEntry {
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

// Determine log level from message content
function detectLogLevel(message: string): 'info' | 'success' | 'warning' | 'error' {
  const lowerMsg = message.toLowerCase();
  if (lowerMsg.includes('error') || lowerMsg.includes('failed')) return 'error';
  if (lowerMsg.includes('warning') || lowerMsg.includes('warn') || lowerMsg.includes('may need')) return 'warning';
  if (lowerMsg.includes('complete') || lowerMsg.includes('saved') || lowerMsg.includes('kept') || lowerMsg.includes('+ ')) return 'success';
  return 'info';
}

export default function LogConsole({ taskId, onComplete }: LogConsoleProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<string>('running');
  const containerRef = useRef<HTMLDivElement>(null);

  // Memoize onComplete to avoid re-creating EventSource
  const handleComplete = useCallback((newStatus: string) => {
    onComplete(newStatus);
  }, [onComplete]);

  useEffect(() => {
    // Connect to backend SSE endpoint (port 8000, correct path order)
    const eventSource = new EventSource(`http://localhost:8000/api/scrape/logs/${taskId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'log') {
          // Backend sends {type: 'log', message: string}
          const timestamp = new Date().toLocaleTimeString();
          const level = detectLogLevel(data.message);
          setLogs((prev) => [...prev, { timestamp, level, message: data.message }]);
        } else if (data.type === 'status') {
          setStatus(data.status);
          if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
            eventSource.close();
            handleComplete(data.status);
          }
        }
      } catch (e) {
        console.error('Failed to parse log:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setStatus('error');
      handleComplete('error');
    };

    return () => {
      eventSource.close();
    };
  }, [taskId, handleComplete]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'success':
        return 'text-emerald-300';
      case 'warning':
        return 'text-amber-300';
      case 'error':
        return 'text-red-300';
      case 'info':
      default:
        return 'text-blue-300';
    }
  };

  const getLevelLabel = (level: string) => {
    switch (level) {
      case 'success':
        return '[SUCCESS]';
      case 'warning':
        return '[WARN]';
      case 'error':
        return '[ERROR]';
      case 'info':
      default:
        return '[INFO]';
    }
  };

  return (
    <div className="bg-black border border-stone-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 border-b border-stone-800 flex items-center justify-between">
        <span className="font-mono text-xs text-stone-500 uppercase tracking-widest">
          Console
        </span>
        <span className={`font-mono text-xs px-2 py-0.5 rounded ${
          status === 'running'
            ? 'bg-[rgba(217,119,87,0.15)] text-[#E8A090] border border-[rgba(217,119,87,0.25)]'
            : status === 'completed'
            ? 'bg-[rgba(16,185,129,0.15)] text-emerald-300 border border-[rgba(16,185,129,0.25)]'
            : 'bg-[rgba(239,68,68,0.15)] text-red-300 border border-[rgba(239,68,68,0.25)]'
        }`}>
          {status.toUpperCase()}
        </span>
      </div>

      {/* Log output */}
      <div
        ref={containerRef}
        className="p-4 max-h-64 overflow-y-auto font-mono text-sm leading-relaxed"
        aria-live="polite"
        aria-atomic="false"
        role="log"
      >
        {logs.length === 0 ? (
          <div className="text-stone-600">Waiting for logs...</div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-stone-600 shrink-0">{log.timestamp}</span>
              <span className={`shrink-0 ${getLevelColor(log.level)}`}>
                {getLevelLabel(log.level)}
              </span>
              <span className="text-stone-400">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
