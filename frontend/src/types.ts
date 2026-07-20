export type Building = {
  id: number;
  height: number | null;
  source: string;
  geojson: {
    type: string;
    coordinates?: number[][][] | number[][][][];
  };
};

export type Reading = {
  id: number;
  station_id: string;
  source?: string;
  reading_type: string;
  value: number;
  unit: string;
  recorded_at: string;
  lon: number;
  lat: number;
};

export type Forecast = {
  id: number;
  station_id: string;
  reading_type: string;
  predicted_value: number;
  target_time: string;
  model_version: string;
  generated_at: string;
  lon: number;
  lat: number;
  notes?: string | null;
};

export type LiveReadingEvent = {
  station_id: string;
  lon: number;
  lat: number;
  reading_type: string;
  value: number;
  unit: string;
  recorded_at: string;
  source?: string;
  reading_id?: number;
};

export type Pathway = {
  id: number;
  name: string | null;
  source: string;
  geojson: { type: string; coordinates?: number[][] | number[][][] };
};

export type Amenity = {
  id: number;
  name: string | null;
  amenity_type: string;
  source: string;
  lon: number;
  lat: number;
};

export type Incident = {
  id: number;
  external_id: string;
  description: string | null;
  started_at: string | null;
  source: string;
  lon: number;
  lat: number;
};

export type LayerCounts = {
  buildings: number;
  pathways: number;
  amenities: number;
  incidents: number;
  readings: number;
};

export type LayerState = {
  buildings: boolean;
  live: boolean;
  forecast: boolean;
  river: boolean;
  air: boolean;
  pathways: boolean;
  incidents: boolean;
  amenities: boolean;
};

export type MapSelection = {
  kind:
    | "building"
    | "amenity"
    | "incident"
    | "pathway"
    | "sensor"
    | "forecast";
  id: string;
  title: string;
  subtitle?: string;
  details: Array<{ label: string; value: string }>;
  lon: number;
  lat: number;
};

export type CameraCommand =
  | { type: "home" }
  | { type: "top" }
  | { type: "oblique" }
  | { type: "flyTo"; lon: number; lat: number; height?: number; heading?: number };
