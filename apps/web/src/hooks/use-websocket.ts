"use client";

import { useEffect, useRef, useState } from "react";
import type { WSMessage } from "@agnostix/types";

/**
 * Reconnecting WebSocket client for the typed server event envelope.
 * Exponential backoff; no arbitrary polling loops (event-driven per
 * .clinerules §18).
 */
export function useWebSocket(url: string | undefined) {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    if (!url) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      if (stopped) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setConnected(true);
      };
      ws.onmessage = (event) => {
        try {
          setLastMessage(JSON.parse(event.data as string) as WSMessage);
        } catch {
          // ignore malformed frames
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stopped) {
          const delay = Math.min(1000 * 2 ** retryRef.current++, 30_000);
          timer = setTimeout(connect, delay);
        }
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      wsRef.current?.close();
    };
  }, [url]);

  return { lastMessage, connected };
}