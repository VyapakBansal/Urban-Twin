import { useEffect, useMemo, useState } from "react";
import { CesiumMap } from "./CesiumMap";
import { BrandBar } from "./components/BrandBar";
import { CameraToolbar } from "./components/CameraToolbar";
import { DroneControls } from "./components/DroneControls";
import { LayerPanel, type LayerRow } from "./components/LayerPanel";
import { MapErrorBoundary } from "./components/MapErrorBoundary";
import { MobileChrome } from "./components/MobileChrome";
import { SelectionCard } from "./components/SelectionCard";
import { StatusBar } from "./components/StatusBar";
import { useCamera } from "./hooks/useCamera";
import { useHorizonForecasts } from "./hooks/useHorizonForecasts";
import { useDroneTelemetry } from "./hooks/useDroneTelemetry";
import { useSensorSnapshot } from "./hooks/useSensorSnapshot";
import { useTheme } from "./hooks/useTheme";
import { useTwinBootstrap } from "./hooks/useTwinBootstrap";
import { DEFAULT_LAYERS } from "./lib/constants";
import type { CameraCommand, DroneCameraMode, LayerState, MapSelection } from "./types";

function useIsPhone() {
  const [phone, setPhone] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(max-width: 720px)").matches
      : false,
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 720px)");
    const onChange = () => setPhone(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return phone;
}

export default function App() {
  const isPhone = useIsPhone();
  const { theme, toggleTheme } = useTheme();
  const { cameraCommand, cameraCommandKey, runCamera } = useCamera();
  const bootstrap = useTwinBootstrap();
  const [layers, setLayers] = useState<LayerState>({ ...DEFAULT_LAYERS });
  const [horizon, setHorizon] = useState(24);
  const [selection, setSelection] = useState<MapSelection | null>(null);
  const [layersOpen, setLayersOpen] = useState(false);
  const [droneCameraMode, setDroneCameraMode] =
    useState<DroneCameraMode>("free");
  const [photorealisticStatus, setPhotorealisticStatus] = useState<
    "loading" | "ready" | "unavailable"
  >(
    import.meta.env.VITE_CESIUM_ION_TOKEN ? "loading" : "unavailable",
  );

  useEffect(() => {
    // Desktop: layers stay open; phone: start closed so the map is usable
    setLayersOpen(!isPhone);
  }, [isPhone]);

  const wsEnabled =
    layers.live ||
    layers.river ||
    layers.air ||
    layers.wind ||
    layers.humidity ||
    layers.precip;

  const sensors = useSensorSnapshot(bootstrap.seed, wsEnabled);
  const drone = useDroneTelemetry(layers.drone);
  const { forecasts, liveForecasts, predictError, predictLoading } =
    useHorizonForecasts({
      enabled: layers.forecast,
      apiOk: bootstrap.apiOk,
      horizon,
      liveTemp: sensors.liveTemp,
      seedTemp: bootstrap.seed.temp,
      storedForecasts: bootstrap.storedForecasts,
    });

  function toggle(key: keyof LayerState) {
    if (key === "photorealistic") {
      const enabled = !layers.photorealistic;
      if (enabled) setPhotorealisticStatus("loading");
      setLayers((prev) => {
        return {
          ...prev,
          photorealistic: enabled,
          // Keep/restore OSM geometry until textured tiles finish loading.
          buildings: true,
        };
      });
      return;
    }
    if (key === "buildings") {
      setLayers((prev) => {
        const enabled = !prev.buildings;
        return {
          ...prev,
          buildings: enabled,
          photorealistic: enabled ? false : prev.photorealistic,
        };
      });
      return;
    }
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function handlePhotorealisticStatus(status: "loading" | "ready" | "unavailable") {
    setPhotorealisticStatus(status);
    if (status === "ready") {
      setLayers((prev) => ({ ...prev, photorealistic: true, buildings: false }));
    } else if (status === "unavailable") {
      setLayers((prev) => ({ ...prev, photorealistic: false, buildings: true }));
    }
  }

  function flyToLayer(key: keyof LayerState) {
    const { liveTemp, river, air, wind } = sensors;
    const { windGrid, incidents } = bootstrap;
    if (key === "drone" && drone.telemetry) {
      setDroneCameraMode("follow");
      return;
    }
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
    if (key === "wind" && (wind || windGrid[0])) {
      const w = wind ?? { lon: windGrid[0].lon, lat: windGrid[0].lat };
      runCamera({ type: "flyTo", lon: w.lon, lat: w.lat, height: 500 });
      return;
    }
    if (key === "forecast" && forecasts[0]) {
      runCamera({
        type: "flyTo",
        lon: forecasts[0].lon,
        lat: forecasts[0].lat,
        height: 260,
      });
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
    runCamera({ type: "home" });
  }

  function handleCameraCommand(command: CameraCommand) {
    setDroneCameraMode("free");
    runCamera(command);
  }

  function handleSelect(sel: MapSelection | null) {
    setSelection(sel);
    if (sel && isPhone) setLayersOpen(false);
  }

  const layerRows: LayerRow[] = useMemo(() => {
    const { loading, buildings, pathways, amenities, incidents } = bootstrap;
    const { liveTemp, wind, humidity, precip, river, air } = sensors;
    return [
      {
        key: "photorealistic",
        label: "Photorealistic",
        meta:
          photorealisticStatus === "ready"
            ? "3D tiles"
            : photorealisticStatus === "loading"
              ? "loading…"
              : "token needed",
      },
      {
        key: "buildings",
        label: "OSM Buildings",
        meta: loading ? "…" : String(buildings.length),
      },
      {
        key: "drone",
        label: "Drone",
        meta: drone.telemetry
          ? `${drone.telemetry.relative_altitude_m.toFixed(0)} m`
          : drone.status,
      },
      { key: "pathways", label: "Pathways", meta: String(pathways.length) },
      { key: "amenities", label: "Places", meta: String(amenities.length) },
      { key: "incidents", label: "Incidents", meta: String(incidents.length) },
      {
        key: "live",
        label: "Weather",
        meta: liveTemp ? `${liveTemp.value.toFixed(1)}°C` : "—",
      },
      {
        key: "wind",
        label: "Wind",
        meta: wind ? `${wind.value.toFixed(1)} m/s` : "—",
      },
      {
        key: "humidity",
        label: "Humidity",
        meta: humidity ? `${humidity.value.toFixed(0)}%` : "—",
      },
      {
        key: "precip",
        label: "Precip",
        meta: precip ? `${precip.value.toFixed(2)} mm` : "—",
      },
      {
        key: "river",
        label: "River",
        meta: river ? `${river.value.toFixed(2)} m` : "—",
      },
      {
        key: "air",
        label: "Air",
        meta: air ? `${air.value.toFixed(1)}` : "—",
      },
      {
        key: "forecast",
        label: "Forecast",
        meta: forecasts.length ? `+${horizon}h` : "—",
      },
    ];
  }, [
    bootstrap,
    sensors,
    forecasts.length,
    horizon,
    photorealisticStatus,
    drone.telemetry,
    drone.status,
  ]);

  return (
    <div className={`app-shell ${sensors.flash ? "is-live-flash" : ""}`}>
      <MapErrorBoundary>
        <CesiumMap
          buildings={bootstrap.buildings}
          pathways={bootstrap.pathways}
          amenities={bootstrap.amenities}
          incidents={bootstrap.incidents}
          layers={layers}
          liveTemp={layers.live ? sensors.liveTemp : null}
          river={layers.river ? sensors.river : null}
          air={layers.air ? sensors.air : null}
          wind={layers.wind ? sensors.wind : null}
          windDir={layers.wind ? sensors.windDir : null}
          humidity={layers.humidity ? sensors.humidity : null}
          precip={layers.precip ? sensors.precip : null}
          windGrid={layers.wind ? bootstrap.windGrid : []}
          forecasts={layers.forecast ? forecasts : []}
          forecastHorizon={horizon}
          pulseKey={sensors.pulseKey}
          selectionId={selection?.id ?? null}
          onSelect={handleSelect}
          cameraCommand={cameraCommand}
          cameraCommandKey={cameraCommandKey}
          theme={theme}
          lowPower={isPhone}
          onPhotorealisticStatus={handlePhotorealisticStatus}
          droneTelemetry={layers.drone ? drone.telemetry : null}
          droneCameraMode={droneCameraMode}
        />
      </MapErrorBoundary>

      <BrandBar theme={theme} onToggleTheme={toggleTheme} />

      {isPhone && !layersOpen && (
        <MobileChrome onOpen={() => setLayersOpen(true)} />
      )}

      <LayerPanel
        open={layersOpen}
        onClose={() => setLayersOpen(false)}
        rows={layerRows}
        layers={layers}
        onToggle={toggle}
        onFly={flyToLayer}
        horizon={horizon}
        onHorizonChange={setHorizon}
        forecasts={forecasts}
        predictLoading={predictLoading}
        predictError={predictError}
        showPredictHint={!liveForecasts.length}
        error={bootstrap.error}
      />

      <CameraToolbar onCommand={handleCameraCommand} />

      <DroneControls
        visible={layers.drone}
        phone={isPhone}
        status={drone.status}
        telemetry={drone.telemetry}
        controlError={drone.controlError}
        cameraMode={droneCameraMode}
        onCameraMode={setDroneCameraMode}
        sendControl={drone.sendControl}
      />

      {selection && (
        <SelectionCard
          selection={selection}
          onClose={() => setSelection(null)}
          onFly={runCamera}
        />
      )}

      <StatusBar
        apiOk={bootstrap.apiOk}
        wsStatus={sensors.wsStatus}
        buildingCount={
          bootstrap.counts?.buildings ?? bootstrap.buildings.length
        }
        civicCount={
          (bootstrap.counts?.pathways ?? bootstrap.pathways.length) +
          (bootstrap.counts?.amenities ?? bootstrap.amenities.length)
        }
        flash={sensors.flash}
        droneStatus={drone.status}
      />
    </div>
  );
}
