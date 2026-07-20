import type {
  Amenity,
  Building,
  Forecast,
  Incident,
  LayerCounts,
  Pathway,
  Reading,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://127.0.0.1:8001/ws/live";

const AOI_BBOX = "-114.100,51.048,-114.062,51.062";
const WIDE_BBOX = "-114.120,51.040,-114.050,51.070";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${path} → ${res.status} (is the API running on :8000?)`);
  }
  return res.json() as Promise<T>;
}

export function fetchBuildings(limit = 8000): Promise<Building[]> {
  return getJson(`/buildings?bbox=${AOI_BBOX}&limit=${limit}`);
}

export function fetchLatestReadings(): Promise<Reading[]> {
  return getJson(`/readings?limit=80`);
}

export function fetchForecasts(): Promise<Forecast[]> {
  // Latest per (station, reading_type) — includes temp + river_level
  return getJson(`/forecasts`);
}

export function fetchHealth(): Promise<{ status: string }> {
  return getJson(`/health`);
}

export function fetchLayerCounts(): Promise<LayerCounts> {
  return getJson(`/layers/counts`);
}

export function fetchPathways(): Promise<Pathway[]> {
  return getJson(`/layers/pathways?bbox=${AOI_BBOX}&limit=2000`);
}

export function fetchAmenities(): Promise<Amenity[]> {
  return getJson(`/layers/amenities?bbox=${AOI_BBOX}&limit=2000`);
}

export function fetchIncidents(): Promise<Incident[]> {
  return getJson(`/layers/incidents?bbox=${WIDE_BBOX}&limit=500`);
}

export { API_BASE, AOI_BBOX };
