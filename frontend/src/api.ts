import type {
  Amenity,
  Building,
  Forecast,
  Incident,
  LayerCounts,
  Pathway,
  PredictBatchOut,
  PredictOut,
  Reading,
  WindCell,
} from "./types";
import { resolveApiBase, resolveWsUrl } from "./lib/origins";

/** Dev: local API. Prod (nginx): same-origin `/api` + `/ws`. */
export const API_BASE = resolveApiBase(
  import.meta.env.VITE_API_BASE,
  import.meta.env.DEV,
);

export const WS_URL = resolveWsUrl(
  import.meta.env.VITE_WS_URL,
  import.meta.env.DEV,
);

const AOI_BBOX = "-114.100,51.048,-114.062,51.062";
const WIDE_BBOX = "-114.120,51.040,-114.050,51.070";

const ALLOWED_READING_TYPES = new Set([
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

type GetOpts = { signal?: AbortSignal };

async function getJson<T>(path: string, opts: GetOpts = {}): Promise<T> {
  if (!path.startsWith("/")) {
    throw new Error("API path must be absolute on the API host");
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    signal: opts.signal,
    headers: { Accept: "application/json" },
    credentials: "omit", // no cookies — public demo API (OWASP A01 surface small)
    mode: "cors",
  });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  const ctype = res.headers.get("content-type") || "";
  if (!ctype.includes("application/json")) {
    throw new Error("Unexpected response type");
  }
  return res.json() as Promise<T>;
}

export function fetchBuildings(
  limit = 8000,
  opts?: GetOpts,
): Promise<Building[]> {
  const n = Math.min(Math.max(1, limit), 8000);
  return getJson(`/buildings?bbox=${AOI_BBOX}&limit=${n}`, opts);
}

export function fetchLatestReadings(opts?: GetOpts): Promise<Reading[]> {
  return getJson(`/readings?limit=80`, opts);
}

export function fetchForecasts(opts?: GetOpts): Promise<Forecast[]> {
  return getJson(`/forecasts`, opts);
}

export function fetchPredict(
  readingType: string,
  horizonHours: number,
  opts?: GetOpts,
): Promise<PredictOut> {
  if (!ALLOWED_READING_TYPES.has(readingType)) {
    return Promise.reject(new Error("Unsupported reading type"));
  }
  const h = Math.min(Math.max(1, Math.round(horizonHours)), 168);
  return getJson(
    `/predict?reading_type=${encodeURIComponent(readingType)}&horizon_hours=${h}`,
    opts,
  );
}

export function fetchPredictBatch(
  readingType: string,
  horizons: number[],
  opts?: GetOpts,
): Promise<PredictBatchOut> {
  if (!ALLOWED_READING_TYPES.has(readingType)) {
    return Promise.reject(new Error("Unsupported reading type"));
  }
  const hs = horizons
    .map((x) => Math.min(Math.max(1, Math.round(x)), 168))
    .slice(0, 12);
  return getJson(
    `/predict/batch?reading_type=${encodeURIComponent(readingType)}&horizons=${hs.join(",")}`,
    opts,
  );
}

export function fetchHealth(opts?: GetOpts): Promise<{ status: string }> {
  return getJson(`/health`, opts);
}

export function fetchLayerCounts(opts?: GetOpts): Promise<LayerCounts> {
  return getJson(`/layers/counts`, opts);
}

export function fetchPathways(opts?: GetOpts): Promise<Pathway[]> {
  return getJson(`/layers/pathways?bbox=${AOI_BBOX}&limit=2000`, opts);
}

export function fetchAmenities(opts?: GetOpts): Promise<Amenity[]> {
  return getJson(`/layers/amenities?bbox=${AOI_BBOX}&limit=2000`, opts);
}

export function fetchIncidents(opts?: GetOpts): Promise<Incident[]> {
  return getJson(`/layers/incidents?bbox=${WIDE_BBOX}&limit=500`, opts);
}

export function fetchWindGrid(opts?: GetOpts): Promise<WindCell[]> {
  return getJson(`/layers/wind?cols=5&rows=4`, opts);
}

export { AOI_BBOX };
