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
  horizon_hours?: number | null;
};

export type PredictOut = {
  reading_type: string;
  predicted_value: number;
  unit: string;
  target_time: string;
  horizon_hours: number | null;
  model_version: string;
  notes: string | null;
  horizons_trained: number[];
};

export type PredictBatchOut = {
  reading_type: string;
  unit: string;
  model_version: string;
  horizons_trained: number[];
  predictions: PredictOut[];
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

export type DroneTelemetryEvent = {
  event_type: "drone.telemetry";
  drone_id: string;
  sequence: number;
  recorded_at: string;
  lat: number;
  lon: number;
  altitude_m: number;
  relative_altitude_m: number;
  north_m: number;
  east_m: number;
  down_m: number;
  velocity_north_m_s: number;
  velocity_east_m_s: number;
  velocity_down_m_s: number;
  roll_deg: number;
  pitch_deg: number;
  yaw_deg: number;
  armed: boolean;
  flight_mode: string;
  source: string;
};

export type DroneControlCommand = {
  event_type: "drone.control";
  client_id: string;
  sequence: number;
  issued_at: string;
  command: "arm" | "takeoff" | "land" | "disarm" | "velocity_body" | "hold";
  forward_m_s?: number;
  right_m_s?: number;
  down_m_s?: number;
  yaw_rate_deg_s?: number;
  ttl_ms?: number;
};

export type DroneCameraMode = "free" | "follow" | "fpv";

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

export type WindCell = {
  lon: number;
  lat: number;
  speed_ms: number;
  direction_deg: number;
  recorded_at: string;
  source?: string;
};

export type LayerState = {
  photorealistic: boolean;
  buildings: boolean;
  drone: boolean;
  live: boolean;
  forecast: boolean;
  river: boolean;
  air: boolean;
  wind: boolean;
  humidity: boolean;
  precip: boolean;
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
