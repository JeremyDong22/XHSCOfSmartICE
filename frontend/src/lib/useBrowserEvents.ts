// Custom hook for subscribing to real-time browser status updates via SSE
// Version: 1.0 - Initial implementation for real-time browser state synchronization
// Subscribes to /api/browsers/events endpoint and notifies on state changes

import { useEffect, useRef, useCallback } from 'react';

// Event types from the backend
export interface BrowserEvent {
  type: 'connected' | 'browser_opened' | 'browser_closed' | 'browser_login_created' | 'account_deleted';
  account_id?: number;
  timestamp?: string;
  message?: string;
}

interface UseBrowserEventsOptions {
  onBrowserOpened?: (accountId: number) => void;
  onBrowserClosed?: (accountId: number) => void;
  onLoginBrowserCreated?: (accountId: number) => void;
  onAccountDeleted?: (accountId: number) => void;
  onConnected?: () => void;
  onError?: (error: Event) => void;
}

export function useBrowserEvents(options: UseBrowserEventsOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const optionsRef = useRef(options);

  // Keep options ref up to date
  optionsRef.current = options;

  const connect = useCallback(() => {
    // Only run in browser
    if (typeof window === 'undefined') return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const apiHost = window.location.hostname;
    const eventSource = new EventSource(`http://${apiHost}:8000/api/browsers/events`);

    eventSource.onmessage = (event) => {
      try {
        const data: BrowserEvent = JSON.parse(event.data);

        switch (data.type) {
          case 'connected':
            optionsRef.current.onConnected?.();
            break;
          case 'browser_opened':
            if (data.account_id !== undefined) {
              optionsRef.current.onBrowserOpened?.(data.account_id);
            }
            break;
          case 'browser_closed':
            if (data.account_id !== undefined) {
              optionsRef.current.onBrowserClosed?.(data.account_id);
            }
            break;
          case 'browser_login_created':
            if (data.account_id !== undefined) {
              optionsRef.current.onLoginBrowserCreated?.(data.account_id);
            }
            break;
          case 'account_deleted':
            if (data.account_id !== undefined) {
              optionsRef.current.onAccountDeleted?.(data.account_id);
            }
            break;
        }
      } catch (e) {
        console.error('Failed to parse browser event:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Browser events SSE error:', error);
      optionsRef.current.onError?.(error);
      eventSource.close();

      // Reconnect after 3 seconds
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Reconnecting to browser events...');
        connect();
      }, 3000);
    };

    eventSourceRef.current = eventSource;
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  // Return a function to manually reconnect if needed
  return { reconnect: connect };
}
