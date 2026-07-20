import { useEffect, useRef, useState } from "react";
import type { LiveReadingEvent } from "../types";
import { WS_URL } from "../api";
import { safeText } from "../lib/readings";

const ALLOWED_TYPES = new Set([
  "temp",
  "humidity",
  "wind",
  "wind_dir",
  "precip",
  "river_level",
  "river_flow",
  "aqi_pm25",
  "aqi_pm10",
]);

function parseLiveEvent(raw: unknown): LiveReadingEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const reading_type = safeText(o.reading_type, 40);
  if (!ALLOWED_TYPES.has(reading_type)) return null;
  const value = Number(o.value);
  const lon = Number(o.lon);
  const lat = Number(o.lat);
  if (!Number.isFinite(value) || !Number.isFinite(lon) || !Number.isFinite(lat)) {
    return null;
  }
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90) return null;
  return {
    station_id: safeText(o.station_id, 80) || "unknown",
    lon,
    lat,
    reading_type,
    value,
    unit: safeText(o.unit, 24) || "",
    recorded_at: safeText(o.recorded_at, 64) || new Date().toISOString(),
    source: o.source != null ? safeText(o.source, 40) : undefined,
    reading_id:
      typeof o.reading_id === "number" && Number.isFinite(o.reading_id)
        ? o.reading_id
        : undefined,
  };
}

export function useLiveReadings(enabled: boolean) {
  const [latestByType, setLatestByType] = useState<
    Partial<Record<string, LiveReadingEvent>>
  >({});
  const [status, setStatus] = useState<
    "idle" | "connecting" | "open" | "closed"
  >("idle");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      wsRef.current?.close();
      wsRef.current = null;
      setStatus("idle");
      return;
    }

    setStatus("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(WS_URL);
    } catch {
      setStatus("closed");
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onerror = () => setStatus("closed");
    ws.onmessage = (ev) => {
      try {
        if (typeof ev.data !== "string" || ev.data.length > 16_384) return;
        const data = parseLiveEvent(JSON.parse(ev.data));
        if (!data) return;
        setLatestByType((prev) => ({ ...prev, [data.reading_type]: data }));
      } catch {
        /* ignore malformed — DoS / tamper residual on open WS */
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [enabled]);

  return { latestByType, status };
}
