import { useEffect, useRef, useState } from 'react';

interface UseWebSocketOptions {
  onMessage?: (data: unknown) => void;
  enabled?: boolean;
}

export function useWebSocket({ onMessage, enabled = true }: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  // Keep the latest callback without reconnecting when its identity changes
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!enabled) return;

    let disposed = false;
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const token = localStorage.getItem('access_token');
      if (!token) return;

      const wsUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
        .replace('http', 'ws');

      const socket = new WebSocket(`${wsUrl}/api/v1/dashboard/ws?token=${token}`);
      ws = socket;

      socket.onopen = () => {
        setConnected(true);
        // Start ping interval
        const pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping');
          }
        }, 30000);
        socket.addEventListener('close', () => clearInterval(pingInterval));
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type !== 'pong') {
            onMessageRef.current?.(data);
          }
        } catch {
          // ignore parse errors
        }
      };

      socket.onclose = () => {
        setConnected(false);
        // Reconnect after 5 seconds, unless the component has unmounted
        if (!disposed) {
          reconnectTimeout = setTimeout(connect, 5000);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  }, [enabled]);

  return { connected };
}
