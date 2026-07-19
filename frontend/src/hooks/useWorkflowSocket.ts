'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import type { WorkflowProgressEvent, ConversationMessage } from '@/services/workflow.service';

function getWsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window === 'undefined') return 'ws://localhost:8000/api/v1';
  // In local dev (Next.js on :3000), connect directly to the backend on :8000
  // because Next.js rewrites don't support WebSocket proxying.
  // In prod the frontend is served from the same host as the API.
  if (window.location.port === '3000') return 'ws://localhost:8000/api/v1';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/v1`;
}

interface UseWorkflowSocketOptions {
  onProgress?: (event: WorkflowProgressEvent) => void;
  onChatMessage?: (msg: ConversationMessage) => void;
  onComplete?: (event: WorkflowProgressEvent) => void;
  onError?: (event: WorkflowProgressEvent) => void;
  onStateSync?: (event: WorkflowProgressEvent) => void;
}

interface UseWorkflowSocketReturn {
  connected: boolean;
  lastEvent: WorkflowProgressEvent | null;
}

export function useWorkflowSocket(
  sessionId: string | null,
  options: UseWorkflowSocketOptions = {},
): UseWorkflowSocketReturn {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WorkflowProgressEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempt = useRef(0);
  const subscribedSessionRef = useRef<string | null>(null);
  const sessionIdRef = useRef(sessionId);
  const optionsRef = useRef(options);
  const intentionalCloseRef = useRef(false);

  sessionIdRef.current = sessionId;
  optionsRef.current = options;

  const getToken = useCallback(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('access_token');
  }, []);

  const sendJson = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const subscribeToSession = useCallback(
    (sid: string) => {
      if (subscribedSessionRef.current === sid) return;
      if (subscribedSessionRef.current) {
        sendJson({ action: 'unsubscribe', sessionId: subscribedSessionRef.current });
      }
      sendJson({ action: 'subscribe', sessionId: sid });
      subscribedSessionRef.current = sid;
    },
    [sendJson],
  );

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    intentionalCloseRef.current = false;
    const ws = new WebSocket(`${getWsBase()}/ws/workflow?token=${token}`);

    ws.onopen = () => {
      setConnected(true);
      reconnectAttempt.current = 0;
      const currentSid = sessionIdRef.current;
      if (currentSid) {
        subscribedSessionRef.current = null;
        subscribeToSession(currentSid);
      }
    };

    ws.onmessage = (evt) => {
      try {
        const event: WorkflowProgressEvent = JSON.parse(evt.data);
        if (event.type === 'ping') {
          sendJson({ action: 'pong' });
          return;
        }
        if (event.type === 'error') return;

        setLastEvent(event);

        switch (event.type) {
          case 'workflow_progress':
            optionsRef.current.onProgress?.(event);
            if (event.chatMessage) {
              optionsRef.current.onChatMessage?.(event.chatMessage);
            }
            break;
          case 'workflow_complete':
            optionsRef.current.onComplete?.(event);
            if (event.chatMessage) {
              optionsRef.current.onChatMessage?.(event.chatMessage);
            }
            break;
          case 'workflow_error':
            optionsRef.current.onError?.(event);
            if (event.chatMessage) {
              optionsRef.current.onChatMessage?.(event.chatMessage);
            }
            break;
          case 'state_sync':
            optionsRef.current.onStateSync?.(event);
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      if (!intentionalCloseRef.current) {
        const delay = Math.min(1000 * 2 ** reconnectAttempt.current, 10000);
        reconnectAttempt.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  // Stable deps only — sessionId is read from ref inside onopen
  }, [getToken, subscribeToSession, sendJson]);

  // Connect once on mount, tear down on unmount
  useEffect(() => {
    connect();
    return () => {
      intentionalCloseRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
      subscribedSessionRef.current = null;
    };
  }, [connect]);

  // When sessionId changes, subscribe/unsubscribe over the existing connection
  useEffect(() => {
    if (!connected) return;
    if (sessionId) {
      subscribeToSession(sessionId);
    } else if (subscribedSessionRef.current) {
      sendJson({ action: 'unsubscribe', sessionId: subscribedSessionRef.current });
      subscribedSessionRef.current = null;
    }
  }, [sessionId, connected, subscribeToSession, sendJson]);

  return { connected, lastEvent };
}
