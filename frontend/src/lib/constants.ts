import type { LayerState } from "../types";

export const HORIZONS = [1, 2, 3, 6, 12, 24, 48] as const;

export const PREDICT_TYPES = ["temp", "river_level", "aqi_pm25"] as const;

export const DEFAULT_LAYERS: LayerState = {
  photorealistic: Boolean(import.meta.env.VITE_CESIUM_ION_TOKEN),
  buildings: true,
  drone: true,
  live: true,
  forecast: true,
  river: true,
  air: true,
  wind: true,
  humidity: false,
  precip: false,
  pathways: true,
  incidents: true,
  amenities: false,
};

export const THEME_KEY = "urban-twin-theme";

export const AOI_CENTER = { lon: -114.081, lat: 51.053 } as const;
