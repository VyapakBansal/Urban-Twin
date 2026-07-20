import { useEffect, useMemo, useState } from "react";
import { CesiumMap } from "./CesiumMap";
import {
  fetchAmenities,
  fetchBuildings,
  fetchForecasts,
  fetchHealth,
  fetchIncidents,
  fetchLatestReadings,
  fetchLayerCounts,
  fetchPathways,
} from "./api";
import { useLiveReadings } from "./hooks/useLiveReadings";
import type {
  Amenity,
  Building,
  CameraCommand,
  Forecast,
  Incident,
  LayerCounts,
  LayerState,
  LiveReadingEvent,
  MapSelection,
  Pathway,
  Reading,
} from "./types";

function latestMap(readings: Reading[]): Record<string, Reading> {
  const out: Record<string, Reading> = {};
  for (const r of readings) {
    const key = `${r.source || "weather"}:${r.reading_type}`;
    if (!(key in out)) out[key] = r;
    if (!(r.reading_type in out)) out[r.reading_type] = r;
  }
  return out;
}

const DEFAULT_LAYERS: LayerState = {
  buildings: true,
  live: true,
  forecast: true,
  river: true,
  air: true,
  pathways: true,
  incidents: true,
  amenities: true,
};

export default function App() {
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [pathways, setPathways] = useState<Pathway[]>([]);
  const [amenities, setAmenities] = useState<Amenity[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [seed, setSeed] = useState<Record<string, Reading>>({});
  const [counts, setCounts] = useState<LayerCounts | null>(null);
  const [apiOk, setApiOk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pulseKey, setPulseKey] = useState(0);
  const [flash, setFlash] = useState(false);
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const [selection, setSelection] = useState<MapSelection | null>(null);
  const [cameraCommand, setCameraCommand] = useState<CameraCommand | null>(null);
  const [cameraCommandKey, setCameraCommandKey] = useState(0);

  const { latestByType: liveByType, status: wsStatus } = useLiveReadings(
    layers.live || layers.river || layers.air,
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [health, b, readings, fcs, paths, amens, incs, lc] =
          await Promise.all([
            fetchHealth(),
            fetchBuildings(),
            fetchLatestReadings(),
            fetchForecasts(),
            fetchPathways(),
            fetchAmenities(),
            fetchIncidents(),
            fetchLayerCounts(),
          ]);
        if (cancelled) return;
        setApiOk(health.status === "ok");
        setBuildings(b);
        setSeed(latestMap(readings));
        setForecasts(fcs);
        setPathways(paths);
        setAmenities(amens);
        setIncidents(incs);
        setCounts(lc);
        setError(null);
      } catch (e) {
        if (!cancelled) {
          setApiOk(false);
          setError(e instanceof Error ? e.message : "Failed to load twin data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const hit = liveByType.temp || liveByType.river_level || liveByType.aqi_pm25;
    if (!hit) return;
    setPulseKey((k) => k + 1);
    setFlash(true);
    const t = window.setTimeout(() => setFlash(false), 1200);
    return () => window.clearTimeout(t);
  }, [
    liveByType.temp?.reading_id,
    liveByType.river_level?.reading_id,
    liveByType.aqi_pm25?.reading_id,
  ]);

  const toLive = (r: Reading | undefined): LiveReadingEvent | null => {
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
  };

  const liveTemp = useMemo(() => {
    return liveByType.temp ?? toLive(seed.temp);
  }, [liveByType.temp, seed.temp]);

  const river = useMemo(() => {
    return (
      liveByType.river_level ??
      toLive(seed["river:river_level"] || seed.river_level)
    );
  }, [liveByType.river_level, seed]);

  const air = useMemo(() => {
    return (
      liveByType.aqi_pm25 ?? toLive(seed["openaq:aqi_pm25"] || seed.aqi_pm25)
    );
  }, [liveByType.aqi_pm25, seed]);

  function toggle(key: keyof LayerState) {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function runCamera(cmd: CameraCommand) {
    setCameraCommand(cmd);
    setCameraCommandKey((k) => k + 1);
  }

  function flyToLayer(key: keyof LayerState) {
    if (key === "live" && liveTemp) {
      runCamera({ type: "flyTo", lon: liveTemp.lon, lat: liveTemp.lat, height: 240 });
      return;
    }
    if (key === "river" && river) {
      runCamera({ type: "flyTo", lon: river.lon, lat: river.lat, height: 280 });
      return;
    }
    if (key === "air" && air) {
      runCamera({ type: "flyTo", lon: air.lon, lat: air.lat, height: 420 });
      return;
    }
    if (key === "forecast" && forecasts[0]) {
      const fc = forecasts[0];
      runCamera({ type: "flyTo", lon: fc.lon, lat: fc.lat, height: 260 });
      return;
    }
    if (key === "incidents" && incidents[0]) {
      runCamera({
        type: "flyTo",
        lon: incidents[0].lon,
        lat: incidents[0].lat,
        height: 300,
      });
      return;
    }
    if (key === "amenities" && amenities[0]) {
      runCamera({
        type: "flyTo",
        lon: amenities[0].lon,
        lat: amenities[0].lat,
        height: 260,
      });
      return;
    }
    runCamera({ type: "home" });
  }

  const layerRows: Array<[keyof LayerState, string, string]> = [
    ["buildings", "Buildings", loading ? "…" : String(buildings.length)],
    ["pathways", "Pathways", String(pathways.length)],
    ["amenities", "Cafés · parks · transit", String(amenities.length)],
    ["incidents", "Traffic incidents", String(incidents.length)],
    ["live", "Live weather", liveTemp ? `${liveTemp.value.toFixed(1)}°C` : "—"],
    ["river", "Bow River", river ? `${river.value.toFixed(2)} ${river.unit}` : "—"],
    ["air", "Air (PM2.5)", air ? `${air.value.toFixed(1)}` : "—"],
    [
      "forecast",
      "Forecast +24h",
      forecasts.length
        ? forecasts
            .map((f) =>
              f.reading_type === "river_level"
                ? `${f.predicted_value.toFixed(2)}m`
                : `${f.predicted_value.toFixed(1)}°C`,
            )
            .join(" · ")
        : "—",
    ],
  ];

  return (
    <div className={`app-shell ${flash ? "is-live-flash" : ""}`}>
      <CesiumMap
        buildings={buildings}
        pathways={pathways}
        amenities={amenities}
        incidents={incidents}
        layers={layers}
        liveTemp={layers.live ? liveTemp : null}
        river={layers.river ? river : null}
        air={layers.air ? air : null}
        forecasts={layers.forecast ? forecasts : []}
        pulseKey={pulseKey}
        selectionId={selection?.id ?? null}
        onSelect={setSelection}
        cameraCommand={cameraCommand}
        cameraCommandKey={cameraCommandKey}
      />

      <header className="brand-bar">
        <p className="brand">Urban Twin</p>
        <p className="place">Kensington · Calgary</p>
        <p className="tagline">
          Hillhurst–Sunnyside digital twin — click anything on the map to
          inspect it
        </p>
      </header>

      <aside className="layer-panel" aria-label="Twin layers">
        <p className="panel-title">City systems</p>
        {layerRows.map(([key, label, meta]) => (
          <div key={key} className="layer-row">
            <input
              type="checkbox"
              checked={layers[key]}
              onChange={() => toggle(key)}
              aria-label={`Toggle ${label}`}
            />
            <button
              type="button"
              className="layer-fly"
              onClick={() => flyToLayer(key)}
              title={`Fly to ${label}`}
            >
              <span className="layer-label">{label}</span>
              <span className="layer-meta">{meta}</span>
            </button>
          </div>
        ))}
        {error && <p className="error">{error}</p>}
      </aside>

      <div className="cam-toolbar" role="toolbar" aria-label="Camera">
        <button type="button" onClick={() => runCamera({ type: "home" })}>
          Home
        </button>
        <button type="button" onClick={() => runCamera({ type: "oblique" })}>
          Street
        </button>
        <button type="button" onClick={() => runCamera({ type: "top" })}>
          Top-down
        </button>
        {liveTemp && (
          <button
            type="button"
            onClick={() =>
              runCamera({
                type: "flyTo",
                lon: liveTemp.lon,
                lat: liveTemp.lat,
                height: 220,
              })
            }
          >
            Weather
          </button>
        )}
        {river && (
          <button
            type="button"
            onClick={() =>
              runCamera({
                type: "flyTo",
                lon: river.lon,
                lat: river.lat,
                height: 260,
              })
            }
          >
            River
          </button>
        )}
      </div>

      {selection && (
        <aside className="select-card" aria-live="polite">
          <div className="select-head">
            <div>
              <p className="select-kind">{selection.kind}</p>
              <h2 className="select-title">{selection.title}</h2>
              {selection.subtitle && (
                <p className="select-sub">{selection.subtitle}</p>
              )}
            </div>
            <button
              type="button"
              className="select-close"
              onClick={() => setSelection(null)}
              aria-label="Close selection"
            >
              Close
            </button>
          </div>
          <dl className="select-dl">
            {selection.details.map((d) => (
              <div key={d.label} className="select-row">
                <dt>{d.label}</dt>
                <dd>{d.value}</dd>
              </div>
            ))}
          </dl>
          <button
            type="button"
            className="select-fly"
            onClick={() =>
              runCamera({
                type: "flyTo",
                lon: selection.lon,
                lat: selection.lat,
                height: selection.kind === "building" ? 160 : 220,
              })
            }
          >
            Fly to feature
          </button>
        </aside>
      )}

      <footer className="pipeline-bar">
        <div className="pipeline-title">30-second story</div>
        <p className="pipeline-copy">
          This is a <em>neighbourhood digital twin</em>: 3D OSM buildings in
          PostGIS, Bow River levels, air quality, Calgary pathways &amp;
          incidents, and live weather — all feeding one map through the same
          ingest → database → Kafka → browser pipeline.
        </p>
        <div className="pipeline-flow">
          <span>Ingest</span>
          <span className="arrow">→</span>
          <span>PostGIS</span>
          <span className="arrow">→</span>
          <span>Kafka</span>
          <span className="arrow">→</span>
          <span>Map</span>
        </div>
        <div className="pipeline-status">
          <span className={apiOk ? "ok" : "bad"}>API {apiOk ? "up" : "down"}</span>
          <span className={wsStatus === "open" ? "ok" : "bad"}>WS {wsStatus}</span>
          <span className={buildings.length ? "ok" : "bad"}>
            {counts?.buildings ?? buildings.length} buildings
          </span>
          <span className={pathways.length || amenities.length ? "ok" : "bad"}>
            {(counts?.pathways ?? pathways.length) +
              (counts?.amenities ?? amenities.length)}{" "}
            civic features
          </span>
          {flash && <span className="flash-pill">live update</span>}
        </div>
        <p className="hint">
          Drag to orbit · scroll zoom · click to inspect · double-click to fly ·
          layer names fly the camera
        </p>
      </footer>
    </div>
  );
}
