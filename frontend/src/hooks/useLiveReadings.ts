import { useEffect, useRef, useState } from "react";
import type { LiveReadingEvent } from "../types";
import { WS_URL } from "../api";

export function useLiveReadings(enabled: boolean) {
  const [latestByType, setLatestByType] = useState<
    Partial<Record<string, LiveReadingEvent>>
  >({});
  const [status, setStatus] = useState<"idle" | "connecting" | "open" | "closed">(
    "idle",
  );
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      wsRef.current?.close();
      wsRef.current = null;
      setStatus("idle");
      return;
    }

    setStatus("connecting");
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onerror = () => setStatus("closed");
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string) as LiveReadingEvent;
        setLatestByType((prev) => ({ ...prev, [data.reading_type]: data }));
      } catch {
        /* ignore malformed */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [enabled]);

  return { latestByType, status };
}
