import type { Forecast, LiveReadingEvent, Reading } from "../types";

export function latestReadingMap(
  readings: Reading[],
): Record<string, Reading> {
  const out: Record<string, Reading> = {};
  for (const r of readings) {
    const key = `${r.source || "weather"}:${r.reading_type}`;
    if (!(key in out)) out[key] = r;
    if (!(r.reading_type in out)) out[r.reading_type] = r;
  }
  return out;
}

export function readingToLive(
  r: Reading | undefined,
): LiveReadingEvent | null {
  if (!r) return null;
  return {
    station_id: r.station_id,
    lon: r.lon,
    lat: r.lat,
    reading_type: r.reading_type,
    value: r.value,
    unit: r.unit,
    recorded_at: r.recorded_at,
    source: r.source,
    reading_id: r.id,
  };
}

export function formatForecastMeta(f: Forecast): string {
  if (f.reading_type === "river_level") {
    return `${f.predicted_value.toFixed(2)} m`;
  }
  if (f.reading_type === "aqi_pm25") {
    return `${f.predicted_value.toFixed(1)} µg`;
  }
  return `${f.predicted_value.toFixed(1)}°C`;
}

export function forecastLabel(readingType: string): string {
  if (readingType === "temp") return "Temp";
  if (readingType === "river_level") return "River";
  if (readingType === "aqi_pm25") return "PM2.5";
  return readingType;
}

/** Strip control chars from untrusted API strings before display (OWASP A03). */
export function safeText(raw: unknown, max = 240): string {
  if (raw == null) return "";
  return String(raw)
    .replace(/[\u0000-\u001F\u007F]/g, "")
    .slice(0, max);
}
