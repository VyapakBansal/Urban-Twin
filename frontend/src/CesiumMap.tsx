import { useEffect, useRef, useState } from "react";
import {
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  Color,
  ConstantPositionProperty,
  ConstantProperty,
  createGooglePhotorealistic3DTileset,
  Credit,
  defined,
  EllipsoidTerrainProvider,
  Entity,
  HeadingPitchRoll,
  Ion,
  Matrix4,
  Rectangle,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  UrlTemplateImageryProvider,
  Viewer,
  Transforms,
  Math as CesiumMath,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import type {
  Amenity,
  Building,
  CameraCommand,
  DroneCameraMode,
  DroneTelemetryEvent,
  Forecast,
  Incident,
  LayerState,
  LiveReadingEvent,
  MapSelection,
  Pathway,
  WindCell,
} from "./types";

const ION = import.meta.env.VITE_CESIUM_ION_TOKEN as string | undefined;
if (ION) Ion.defaultAccessToken = ION;

const CENTER = { lon: -114.081, lat: 51.053 };
const AOI = { west: -114.1, south: 51.048, east: -114.062, north: 51.062 };

type EntityMeta = MapSelection;

type Props = {
  buildings: Building[];
  pathways: Pathway[];
  amenities: Amenity[];
  incidents: Incident[];
  layers: LayerState;
  liveTemp: LiveReadingEvent | null;
  river: LiveReadingEvent | null;
  air: LiveReadingEvent | null;
  wind: LiveReadingEvent | null;
  windDir: LiveReadingEvent | null;
  humidity: LiveReadingEvent | null;
  precip: LiveReadingEvent | null;
  windGrid: WindCell[];
  forecasts: Forecast[];
  forecastHorizon: number;
  pulseKey: number;
  selectionId: string | null;
  onSelect: (sel: MapSelection | null) => void;
  cameraCommand: CameraCommand | null;
  cameraCommandKey: number;
  theme: "dark" | "light";
  lowPower: boolean;
  onPhotorealisticStatus: (status: "loading" | "ready" | "unavailable") => void;
  droneTelemetry: DroneTelemetryEvent | null;
  droneCameraMode: DroneCameraMode;
};

function heightForBuilding(b: Building): number {
  if (b.height && b.height > 3) return Math.min(b.height, 80);
  return 8 + (b.id % 7) * 3.5;
}

function facadeColor(b: Building, selected: boolean): Color {
  const h = heightForBuilding(b);
  let base: Color;
  if (h > 28) base = Color.fromCssColorString("#e8c9a0");
  else if (h > 16) base = Color.fromCssColorString("#c9b08a");
  else base = Color.fromCssColorString("#9a8b78");
  return selected ? Color.fromCssColorString("#f59e0b").withAlpha(0.95) : base.withAlpha(0.92);
}

function amenityColor(t: string): Color {
  if (t === "transit") return Color.fromCssColorString("#f472b6");
  if (t === "park") return Color.fromCssColorString("#4ade80");
  if (t === "cafe" || t === "restaurant") return Color.fromCssColorString("#fbbf24");
  return Color.fromCssColorString("#a3a3a3");
}

function centroid(ring: number[][]): { lon: number; lat: number } {
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (const c of ring) {
    if (c.length < 2) continue;
    sx += c[0];
    sy += c[1];
    n += 1;
  }
  return n ? { lon: sx / n, lat: sy / n } : { lon: CENTER.lon, lat: CENTER.lat };
}

function flyHome(viewer: Viewer, duration = 1.4) {
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(CENTER.lon, CENTER.lat - 0.006, 650),
    orientation: {
      heading: CesiumMath.toRadians(15),
      pitch: CesiumMath.toRadians(-42),
      roll: 0,
    },
    duration,
  });
}

function applyCamera(viewer: Viewer, cmd: CameraCommand) {
  if (cmd.type === "home") {
    flyHome(viewer);
    return;
  }
  if (cmd.type === "top") {
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(CENTER.lon, CENTER.lat, 2200),
      orientation: {
        heading: 0,
        pitch: CesiumMath.toRadians(-90),
        roll: 0,
      },
      duration: 1.2,
    });
    return;
  }
  if (cmd.type === "oblique") {
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(CENTER.lon + 0.004, CENTER.lat - 0.01, 480),
      orientation: {
        heading: CesiumMath.toRadians(-28),
        pitch: CesiumMath.toRadians(-28),
        roll: 0,
      },
      duration: 1.4,
    });
    return;
  }
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(
      cmd.lon,
      cmd.lat - 0.0018,
      cmd.height ?? 220,
    ),
    orientation: {
      heading: CesiumMath.toRadians(cmd.heading ?? 20),
      pitch: CesiumMath.toRadians(-35),
      roll: 0,
    },
    duration: 1.35,
  });
}

function windTip(
  lon: number,
  lat: number,
  directionDeg: number,
  speedMs: number,
): { lon: number; lat: number } {
  // Meteorological direction = FROM; arrow shows flow TOWARD
  const toward = ((directionDeg + 180) % 360) * (Math.PI / 180);
  const scale = 0.00032 * Math.min(Math.max(speedMs, 0.5), 14);
  return {
    lon: lon + Math.sin(toward) * scale,
    lat: lat + Math.cos(toward) * scale,
  };
}

/** Flat ground pin — point + thin ring. No cones / pulsing volumes. */
function groundPinOpts(colorCss: string, ringM = 22) {
  const fill = Color.fromCssColorString(colorCss);
  return {
    point: {
      pixelSize: 9,
      color: fill.withAlpha(0.95),
      outlineColor: Color.fromCssColorString("#f5f0e8").withAlpha(0.85),
      outlineWidth: 1.5,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
    ellipse: {
      semiMajorAxis: ringM,
      semiMinorAxis: ringM,
      material: fill.withAlpha(0.1),
      outline: true,
      outlineColor: fill.withAlpha(0.55),
      height: 1.2,
    },
  };
}

function applyBasemap(viewer: Viewer, theme: "dark" | "light") {
  viewer.imageryLayers.removeAll();
  const url =
    theme === "light"
      ? "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
      : "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png";
  viewer.imageryLayers.addImageryProvider(
    new UrlTemplateImageryProvider({
      url,
      credit: new Credit("© OpenStreetMap contributors © CARTO", true),
    }),
  );
  const bg = theme === "light" ? "#e8e4dc" : "#0b0f14";
  viewer.scene.globe.baseColor = Color.fromCssColorString(bg);
  viewer.scene.backgroundColor = Color.fromCssColorString(bg);
}

export function CesiumMap({
  buildings,
  pathways,
  amenities,
  incidents,
  layers,
  liveTemp,
  river,
  air,
  wind,
  windDir,
  humidity,
  precip,
  windGrid,
  forecasts,
  forecastHorizon,
  pulseKey: _pulseKey,
  selectionId,
  onSelect,
  cameraCommand,
  cameraCommandKey,
  theme,
  lowPower,
  onPhotorealisticStatus,
  droneTelemetry,
  droneCameraMode,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const photorealisticRef = useRef<Cesium3DTileset | null>(null);
  const photorealisticLoadingRef = useRef(false);
  const droneEntityRef = useRef<Entity | null>(null);
  const themeRef = useRef(theme);
  themeRef.current = theme;
  const onPhotorealisticStatusRef = useRef(onPhotorealisticStatus);
  onPhotorealisticStatusRef.current = onPhotorealisticStatus;
  const ids = useRef<Record<string, string[]>>({
    buildings: [],
    pathways: [],
    amenities: [],
    incidents: [],
    wind: [],
  });
  const beacons = useRef<Record<string, Entity | null>>({
    live: null,
    river: null,
    air: null,
    humidity: null,
    precip: null,
    windStation: null,
  });
  const forecastEntities = useRef<Entity[]>([]);
  const metaRef = useRef<Map<string, EntityMeta>>(new Map());
  const highlightRef = useRef<Entity | null>(null);
  const didFly = useRef(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;
    const viewer = new Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      baseLayerPicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      terrainProvider: new EllipsoidTerrainProvider(),
      baseLayer: false,
    });
    applyBasemap(viewer, themeRef.current);
    viewer.scene.fog.enabled = true;
    viewer.scene.fog.density = 0.00035;
    const ctrl = viewer.scene.screenSpaceCameraController;
    ctrl.minimumZoomDistance = 80;
    ctrl.maximumZoomDistance = 12000;
    ctrl.enableCollisionDetection = true;

    viewer.camera.setView({
      destination: Cartesian3.fromDegrees(CENTER.lon, CENTER.lat - 0.008, 900),
      orientation: {
        heading: CesiumMath.toRadians(0),
        pitch: CesiumMath.toRadians(-38),
        roll: 0,
      },
    });
    viewer.entities.add({
      id: "aoi-bounds",
      rectangle: {
        coordinates: Rectangle.fromDegrees(AOI.west, AOI.south, AOI.east, AOI.north),
        material: Color.fromCssColorString("#d4a373").withAlpha(0.04),
        outline: true,
        outlineColor: Color.fromCssColorString("#d4a373").withAlpha(0.45),
        height: 0.5,
      },
    });

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((movement: { endPosition: Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.endPosition);
      const canvas = viewer.scene.canvas;
      if (defined(picked) && picked.id && typeof picked.id !== "string") {
        const ent = picked.id as Entity;
        canvas.style.cursor = metaRef.current.has(String(ent.id)) ? "pointer" : "grab";
      } else {
        canvas.style.cursor = "grab";
      }
    }, ScreenSpaceEventType.MOUSE_MOVE);

    handler.setInputAction((click: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(click.position);
      if (!defined(picked) || !picked.id || typeof picked.id === "string") {
        onSelectRef.current(null);
        return;
      }
      const ent = picked.id as Entity;
      const meta = metaRef.current.get(String(ent.id));
      if (!meta) {
        onSelectRef.current(null);
        return;
      }
      onSelectRef.current(meta);
    }, ScreenSpaceEventType.LEFT_CLICK);

    handler.setInputAction((click: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(click.position);
      if (!defined(picked) || !picked.id || typeof picked.id === "string") return;
      const ent = picked.id as Entity;
      const meta = metaRef.current.get(String(ent.id));
      if (!meta) return;
      onSelectRef.current(meta);
      applyCamera(viewer, {
        type: "flyTo",
        lon: meta.lon,
        lat: meta.lat,
        height: meta.kind === "building" ? 180 : 220,
      });
    }, ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

    viewerRef.current = viewer;

    const resize = () => {
      try {
        viewer.resize();
        viewer.scene.requestRender();
      } catch {
        /* destroyed */
      }
    };
    resize();
    requestAnimationFrame(resize);
    window.addEventListener("resize", resize);
    window.addEventListener("orientationchange", resize);
    const ro =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => resize())
        : null;
    if (containerRef.current && ro) ro.observe(containerRef.current);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("orientationchange", resize);
      ro?.disconnect();
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
      photorealisticRef.current = null;
      photorealisticLoadingRef.current = false;
      didFly.current = false;
      metaRef.current.clear();
    };
  }, []);

  // Google tiles ship baked real-world lighting and their own terrain, so the
  // globe/basemap is hidden and Cesium lighting/shadows/post-FX stay OFF —
  // stacking them on the tiles causes striping and a washed-out picture.
  const [photoActive, setPhotoActive] = useState(false);
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.scene.globe.show = !photoActive;
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = photoActive;
    viewer.shadows = false;
    viewer.scene.postProcessStages.ambientOcclusion.enabled = false;
    viewer.scene.postProcessStages.bloom.enabled = false;
    // Fog washes out distant tiles; the imagery baked into them already fades.
    viewer.scene.fog.enabled = !photoActive;
    viewer.scene.fog.density = 0.00035;
    // Render at native device resolution + MSAA for crisp tiles.
    viewer.useBrowserRecommendedResolution = !(photoActive && !lowPower);
    viewer.scene.msaaSamples = photoActive && !lowPower ? 4 : 1;
    const tileset = photorealisticRef.current;
    if (tileset) {
      // Conserve tile quota: default-quality SSE, distance-based detail decay,
      // no speculative preloading, and a large cache to avoid re-fetching.
      tileset.maximumScreenSpaceError = lowPower ? 32 : 16;
      tileset.dynamicScreenSpaceError = true;
      tileset.skipLevelOfDetail = true;
      tileset.preloadWhenHidden = false;
      tileset.preloadFlightDestinations = false;
      tileset.cacheBytes = 512 * 1024 * 1024;
      tileset.maximumCacheOverflowBytes = 256 * 1024 * 1024;
    }
    // Let the camera get close to street level on textured tiles, but not
    // zoom out far enough to stream the whole city.
    viewer.scene.screenSpaceCameraController.minimumZoomDistance = photoActive ? 15 : 80;
    viewer.scene.screenSpaceCameraController.maximumZoomDistance = photoActive
      ? 4000
      : 12000;
    viewer.scene.requestRender();
  }, [photoActive, lowPower]);

  // Keep the camera inside the AOI while photorealistic tiles are active so
  // only the neighborhood is streamed (each tile request costs quota).
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !photoActive) return;
    const MARGIN = 0.012;
    const MAX_CAMERA_HEIGHT = 3200; // ellipsoid height; Kensington ground ≈ 1030 m
    const clampToAoi = () => {
      const carto = viewer.camera.positionCartographic;
      const lon = CesiumMath.toDegrees(carto.longitude);
      const lat = CesiumMath.toDegrees(carto.latitude);
      const clampedLon = Math.min(Math.max(lon, AOI.west - MARGIN), AOI.east + MARGIN);
      const clampedLat = Math.min(Math.max(lat, AOI.south - MARGIN), AOI.north + MARGIN);
      const clampedHeight = Math.min(carto.height, MAX_CAMERA_HEIGHT);
      if (clampedLon === lon && clampedLat === lat && clampedHeight === carto.height) {
        return;
      }
      viewer.camera.setView({
        destination: Cartesian3.fromDegrees(clampedLon, clampedLat, clampedHeight),
        orientation: {
          heading: viewer.camera.heading,
          pitch: viewer.camera.pitch,
          roll: viewer.camera.roll,
        },
      });
    };
    viewer.camera.moveEnd.addEventListener(clampToAoi);
    clampToAoi();
    return () => {
      viewer.camera.moveEnd.removeEventListener(clampToAoi);
    };
  }, [photoActive]);

  // Google Photorealistic 3D Tiles are the textured-building source. OSM
  // extrusions remain visible until this resolves, and are restored on error.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    if (!layers.photorealistic) {
      if (photorealisticRef.current) photorealisticRef.current.show = false;
      setPhotoActive(false);
      return;
    }
    if (!ION) {
      onPhotorealisticStatusRef.current("unavailable");
      setPhotoActive(false);
      return;
    }
    if (photorealisticRef.current) {
      photorealisticRef.current.show = true;
      onPhotorealisticStatusRef.current("ready");
      setPhotoActive(true);
      return;
    }
    if (photorealisticLoadingRef.current) return;

    photorealisticLoadingRef.current = true;
    onPhotorealisticStatusRef.current("loading");
    void createGooglePhotorealistic3DTileset()
      .then((tileset) => {
        if (viewer.isDestroyed()) {
          tileset.destroy();
          return;
        }
        viewer.scene.primitives.add(tileset);
        photorealisticRef.current = tileset;
        photorealisticLoadingRef.current = false;
        onPhotorealisticStatusRef.current("ready");
        setPhotoActive(true);
        viewer.scene.requestRender();
      })
      .catch((error: unknown) => {
        photorealisticLoadingRef.current = false;
        console.warn(
          "Google Photorealistic 3D Tiles unavailable; restoring OSM buildings.",
          error,
        );
        onPhotorealisticStatusRef.current("unavailable");
        setPhotoActive(false);
      });
  }, [layers.photorealistic]);

  // One persistent drone entity: update properties in place at telemetry rate.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (!droneTelemetry || !layers.drone) {
      if (droneEntityRef.current) droneEntityRef.current.show = false;
      return;
    }

    const position = Cartesian3.fromDegrees(
      droneTelemetry.lon,
      droneTelemetry.lat,
      droneTelemetry.altitude_m,
    );
    const attitude = new HeadingPitchRoll(
      CesiumMath.toRadians(droneTelemetry.yaw_deg),
      CesiumMath.toRadians(droneTelemetry.pitch_deg),
      CesiumMath.toRadians(droneTelemetry.roll_deg),
    );
    const orientation = Transforms.headingPitchRollQuaternion(position, attitude);

    if (!droneEntityRef.current) {
      droneEntityRef.current = viewer.entities.add({
        id: "live-drone",
        position,
        orientation,
        box: {
          dimensions: new Cartesian3(1.1, 0.7, 0.22),
          material: Color.fromCssColorString("#f59e0b").withAlpha(0.92),
          outline: true,
          outlineColor: Color.WHITE.withAlpha(0.8),
        },
        point: {
          pixelSize: 8,
          color: Color.fromCssColorString("#f59e0b"),
          outlineColor: Color.WHITE,
          outlineWidth: 2,
          disableDepthTestDistance: 800,
        },
      });
    } else {
      droneEntityRef.current.show = true;
      droneEntityRef.current.position = new ConstantPositionProperty(position);
      droneEntityRef.current.orientation = new ConstantProperty(orientation);
    }

    if (droneCameraMode === "fpv") {
      viewer.camera.setView({
        destination: Cartesian3.fromDegrees(
          droneTelemetry.lon,
          droneTelemetry.lat,
          droneTelemetry.altitude_m + 0.25,
        ),
        orientation: {
          heading: attitude.heading,
          pitch: attitude.pitch,
          roll: attitude.roll,
        },
      });
    } else if (droneCameraMode === "follow") {
      const range = 55;
      const localOffset = new Cartesian3(
        -Math.sin(attitude.heading) * range,
        -Math.cos(attitude.heading) * range,
        22,
      );
      const frame = Transforms.eastNorthUpToFixedFrame(position);
      const destination = Matrix4.multiplyByPoint(
        frame,
        localOffset,
        new Cartesian3(),
      );
      viewer.camera.setView({
        destination,
        orientation: {
          heading: attitude.heading,
          pitch: CesiumMath.toRadians(-22),
          roll: 0,
        },
      });
    }
    viewer.scene.requestRender();
  }, [droneTelemetry, droneCameraMode, layers.drone]);

  // Camera commands from toolbar / layer panel
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !cameraCommand || cameraCommandKey === 0) return;
    applyCamera(viewer, cameraCommand);
  }, [cameraCommand, cameraCommandKey]);

  // Light / dark basemap (skip first paint — init already applied)
  const themeReady = useRef(false);
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (!themeReady.current) {
      themeReady.current = true;
      return;
    }
    applyBasemap(viewer, theme);
  }, [theme]);

  // Selection ring
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (highlightRef.current) {
      viewer.entities.remove(highlightRef.current);
      highlightRef.current = null;
    }
    if (!selectionId) return;
    const meta = metaRef.current.get(selectionId);
    if (!meta) return;
    highlightRef.current = viewer.entities.add({
      id: "selection-ring",
      position: Cartesian3.fromDegrees(meta.lon, meta.lat, 1),
      ellipse: {
        semiMajorAxis: meta.kind === "building" ? 28 : 32,
        semiMinorAxis: meta.kind === "building" ? 28 : 32,
        material: Color.fromCssColorString("#d4a373").withAlpha(0.08),
        outline: true,
        outlineColor: Color.fromCssColorString("#d4a373").withAlpha(0.75),
        height: 1.5,
      },
    });
  }, [selectionId, buildings, amenities, incidents, pathways, liveTemp, river, air, forecasts]);

  const clearGroup = (viewer: Viewer, key: string) => {
    for (const id of ids.current[key] || []) {
      viewer.entities.removeById(id);
      metaRef.current.delete(id);
    }
    ids.current[key] = [];
  };

  // Buildings
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    clearGroup(viewer, "buildings");
    if (!layers.buildings) return;
    for (const b of buildings) {
      const g = b.geojson;
      if (!g?.coordinates) continue;
      const rings: number[][][] =
        g.type === "Polygon"
          ? (g.coordinates as number[][][])
          : g.type === "MultiPolygon"
            ? (g.coordinates as number[][][][]).map((p) => p[0])
            : [];
      rings.forEach((ring, i) => {
        if (!ring || ring.length < 3) return;
        const positions = ring.flatMap((c) => [c[0], c[1]]);
        if (positions.length < 6) return;
        const id = `bldg-${b.id}-${i}`;
        const c = centroid(ring);
        const h = heightForBuilding(b);
        viewer.entities.add({
          id,
          polygon: {
            hierarchy: Cartesian3.fromDegreesArray(positions),
            extrudedHeight: h,
            material: facadeColor(b, false),
            outline: false,
            height: 0,
          },
        });
        metaRef.current.set(id, {
          kind: "building",
          id,
          title: `Building #${b.id}`,
          subtitle: "OSM footprint · PostGIS",
          details: [
            { label: "Height", value: `${h.toFixed(0)} m (est.)` },
            { label: "Source", value: b.source || "osm" },
            { label: "Lon / Lat", value: `${c.lon.toFixed(5)}, ${c.lat.toFixed(5)}` },
          ],
          lon: c.lon,
          lat: c.lat,
        });
        ids.current.buildings.push(id);
      });
    }
    if (ids.current.buildings.length && !didFly.current) {
      didFly.current = true;
      flyHome(viewer, 2.2);
    }
  }, [buildings, layers.buildings]);

  // Pathway lines
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    clearGroup(viewer, "pathways");
    if (!layers.pathways) return;
    for (const p of pathways) {
      const g = p.geojson;
      let coords: number[][] | undefined;
      if (g.type === "LineString") coords = g.coordinates as number[][];
      else if (g.type === "MultiLineString")
        coords = (g.coordinates as number[][][])[0];
      if (!coords || coords.length < 2) continue;
      const positions = coords.flatMap((c) => [c[0], c[1]]);
      const id = `path-${p.id}`;
      const mid = coords[Math.floor(coords.length / 2)];
      viewer.entities.add({
        id,
        polyline: {
          positions: Cartesian3.fromDegreesArray(positions),
          width: 3,
          material: Color.fromCssColorString("#2dd4bf").withAlpha(0.85),
          clampToGround: true,
        },
      });
      metaRef.current.set(id, {
        kind: "pathway",
        id,
        title: p.name || `Pathway #${p.id}`,
        subtitle: "Foot / cycle path",
        details: [
          { label: "Source", value: p.source },
          { label: "Vertices", value: String(coords.length) },
        ],
        lon: mid[0],
        lat: mid[1],
      });
      ids.current.pathways.push(id);
    }
  }, [pathways, layers.pathways]);

  // Amenities
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    clearGroup(viewer, "amenities");
    if (!layers.amenities) return;
    for (const a of amenities) {
      const id = `amen-${a.id}`;
      const selected = selectionId === id;
      viewer.entities.add({
        id,
        position: Cartesian3.fromDegrees(a.lon, a.lat, 8),
        point: {
          pixelSize: selected
            ? 16
            : a.amenity_type === "transit"
              ? 12
              : 8,
          color: amenityColor(a.amenity_type),
          outlineColor: selected ? Color.fromCssColorString("#fde68a") : Color.WHITE,
          outlineWidth: selected ? 3 : 1,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: selected
          ? {
              text: a.name || a.amenity_type,
              font: "600 11px DM Sans, sans-serif",
              fillColor: Color.WHITE,
              pixelOffset: new Cartesian2(0, -14),
              showBackground: true,
              backgroundColor: Color.fromCssColorString("#831843").withAlpha(0.85),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            }
          : undefined,
      });
      metaRef.current.set(id, {
        kind: "amenity",
        id,
        title: a.name || a.amenity_type,
        subtitle: a.amenity_type,
        details: [
          { label: "Type", value: a.amenity_type },
          { label: "Source", value: a.source },
          { label: "Lon / Lat", value: `${a.lon.toFixed(5)}, ${a.lat.toFixed(5)}` },
        ],
        lon: a.lon,
        lat: a.lat,
      });
      ids.current.amenities.push(id);
    }
  }, [amenities, layers.amenities, selectionId]);

  // Incidents
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    clearGroup(viewer, "incidents");
    if (!layers.incidents) return;
    for (const inc of incidents) {
      const id = `inc-${inc.id}`;
      const selected = selectionId === id;
      viewer.entities.add({
        id,
        position: Cartesian3.fromDegrees(inc.lon, inc.lat, 12),
        point: {
          pixelSize: selected ? 18 : 14,
          color: Color.fromCssColorString("#f87171"),
          outlineColor: selected ? Color.fromCssColorString("#fde68a") : Color.WHITE,
          outlineWidth: selected ? 3 : 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
      metaRef.current.set(id, {
        kind: "incident",
        id,
        title: "Traffic incident",
        subtitle: inc.description?.slice(0, 48) || inc.external_id,
        details: [
          { label: "Detail", value: inc.description || "—" },
          {
            label: "Started",
            value: inc.started_at
              ? new Date(inc.started_at).toLocaleString()
              : "—",
          },
          { label: "Source", value: inc.source },
        ],
        lon: inc.lon,
        lat: inc.lat,
      });
      ids.current.incidents.push(id);
    }
  }, [incidents, layers.incidents, selectionId]);

  // Live weather — ground pin
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.live) {
      metaRef.current.delete("live-sensor");
      viewer.entities.remove(beacons.current.live);
      beacons.current.live = null;
    }
    if (!layers.live || !liveTemp) return;
    const id = "live-sensor";
    const pin = groundPinOpts("#d4a373", 26);
    beacons.current.live = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(liveTemp.lon, liveTemp.lat, 2),
      ...pin,
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Live weather",
      subtitle: `${liveTemp.value.toFixed(1)} ${liveTemp.unit}`,
      details: [
        { label: "Temp", value: `${liveTemp.value.toFixed(1)} ${liveTemp.unit}` },
        { label: "Source", value: liveTemp.source || "openweather" },
        {
          label: "Recorded",
          value: new Date(liveTemp.recorded_at).toLocaleString(),
        },
      ],
      lon: liveTemp.lon,
      lat: liveTemp.lat,
    });
  }, [liveTemp, layers.live]);

  // River — ground pin
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.river) {
      metaRef.current.delete("river-sensor");
      viewer.entities.remove(beacons.current.river);
      beacons.current.river = null;
    }
    if (!layers.river || !river) return;
    const id = "river-sensor";
    const pin = groundPinOpts("#5b9bb8", 26);
    beacons.current.river = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(river.lon, river.lat, 2),
      ...pin,
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Bow River level",
      subtitle: `${river.value.toFixed(2)} ${river.unit}`,
      details: [
        { label: "Level", value: `${river.value.toFixed(3)} ${river.unit}` },
        { label: "Source", value: river.source || "env-canada" },
        {
          label: "Recorded",
          value: new Date(river.recorded_at).toLocaleString(),
        },
      ],
      lon: river.lon,
      lat: river.lat,
    });
  }, [river, layers.river]);

  // Air quality — compact ring (no giant halo)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.air) {
      metaRef.current.delete("air-sensor");
      viewer.entities.remove(beacons.current.air);
      beacons.current.air = null;
    }
    if (!layers.air || !air) return;
    const id = "air-sensor";
    const tone =
      air.value <= 12 ? "#6b9b7a" : air.value <= 35 ? "#c4a574" : "#b86a5a";
    const pin = groundPinOpts(tone, 30);
    beacons.current.air = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(air.lon, air.lat, 2),
      ...pin,
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Air quality",
      subtitle: `PM2.5 ${air.value.toFixed(1)} ${air.unit}`,
      details: [
        { label: "PM2.5", value: `${air.value.toFixed(1)} ${air.unit}` },
        { label: "Source", value: air.source || "openaq" },
        {
          label: "Recorded",
          value: new Date(air.recorded_at).toLocaleString(),
        },
      ],
      lon: air.lon,
      lat: air.lat,
    });
  }, [air, layers.air]);

  // Forecasts — small offset pins (values live in the side panel)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    for (const e of forecastEntities.current) {
      metaRef.current.delete(String(e.id));
      viewer.entities.remove(e);
    }
    forecastEntities.current = [];
    if (!layers.forecast || !forecasts.length) return;

    const palette: Record<string, string> = {
      temp: "#c4a574",
      river_level: "#5b9bb8",
      aqi_pm25: "#6b9b7a",
    };
    const offsets: Record<string, [number, number]> = {
      temp: [0.0009, -0.0003],
      river_level: [0.0018, -0.001],
      aqi_pm25: [-0.0014, 0.0009],
    };

    for (const fc of forecasts) {
      const h = fc.horizon_hours ?? forecastHorizon;
      const id = `forecast-${fc.reading_type}`;
      const [lonOff, latOff] = offsets[fc.reading_type] ?? [0.001, 0];
      const lon = fc.lon + lonOff;
      const lat = fc.lat + latOff;
      const color = palette[fc.reading_type] ?? "#a8a29e";
      const isRiver = fc.reading_type === "river_level";
      const isAir = fc.reading_type === "aqi_pm25";
      const title = isRiver
        ? `River +${h}h`
        : isAir
          ? `PM2.5 +${h}h`
          : `Temp +${h}h`;
      const valueText = isRiver
        ? `${fc.predicted_value.toFixed(3)} m`
        : isAir
          ? `${fc.predicted_value.toFixed(1)} µg/m³`
          : `${fc.predicted_value.toFixed(1)} °C`;
      const pin = groundPinOpts(color, 18);
      const entity = viewer.entities.add({
        id,
        position: Cartesian3.fromDegrees(lon, lat, 2),
        ...pin,
      });
      metaRef.current.set(id, {
        kind: "forecast",
        id,
        title,
        subtitle: fc.model_version,
        details: [
          { label: "Predicted", value: valueText },
          { label: "Horizon", value: `+${h}h` },
          {
            label: "Target",
            value: new Date(fc.target_time).toLocaleString(),
          },
          {
            label: "Generated",
            value: new Date(fc.generated_at).toLocaleString(),
          },
          ...(fc.notes ? [{ label: "Notes", value: fc.notes }] : []),
        ],
        lon,
        lat,
      });
      forecastEntities.current.push(entity);
    }
  }, [forecasts, layers.forecast, forecastHorizon]);

  // Wind field — short muted ticks (pathway-adjacent language)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    clearGroup(viewer, "wind");
    if (!layers.wind || !windGrid.length) return;
    const stroke = Color.fromCssColorString("#8a9aa3").withAlpha(0.75);
    windGrid.forEach((cell, i) => {
      const tip = windTip(cell.lon, cell.lat, cell.direction_deg, cell.speed_ms);
      const id = `wind-${i}`;
      const speed = cell.speed_ms;
      viewer.entities.add({
        id,
        polyline: {
          positions: Cartesian3.fromDegreesArrayHeights([
            cell.lon,
            cell.lat,
            12,
            tip.lon,
            tip.lat,
            12,
          ]),
          width: 1.5,
          material: stroke,
          clampToGround: false,
        },
        position: Cartesian3.fromDegrees(cell.lon, cell.lat, 12),
        point: {
          pixelSize: 3,
          color: stroke,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
      metaRef.current.set(id, {
        kind: "sensor",
        id,
        title: "Wind",
        subtitle: `${speed.toFixed(1)} m/s`,
        details: [
          { label: "Speed", value: `${speed.toFixed(2)} m/s` },
          { label: "From", value: `${cell.direction_deg.toFixed(0)}°` },
          { label: "Source", value: cell.source || "open-meteo" },
          {
            label: "Recorded",
            value: new Date(cell.recorded_at).toLocaleString(),
          },
        ],
        lon: cell.lon,
        lat: cell.lat,
      });
      ids.current.wind.push(id);
    });
  }, [windGrid, layers.wind]);

  // Station wind — single pin (direction shown via grid when on)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.windStation) {
      metaRef.current.delete("wind-station");
      viewer.entities.remove(beacons.current.windStation);
      beacons.current.windStation = null;
    }
    if (!layers.wind || !wind) return;
    // Prefer grid ticks; only show station pin when no grid cells
    if (windGrid.length) return;
    const id = "wind-station";
    const pin = groundPinOpts("#8a9aa3", 20);
    beacons.current.windStation = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(wind.lon, wind.lat, 2),
      ...pin,
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Station wind",
      subtitle: `${wind.value.toFixed(1)} ${wind.unit}`,
      details: [
        { label: "Speed", value: `${wind.value.toFixed(2)} ${wind.unit}` },
        {
          label: "Direction",
          value: windDir ? `${windDir.value.toFixed(0)}°` : "—",
        },
        { label: "Source", value: wind.source || "openweather" },
      ],
      lon: wind.lon,
      lat: wind.lat,
    });
  }, [wind, windDir, layers.wind, windGrid.length]);

  // Humidity — pin only
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.humidity) {
      metaRef.current.delete("humidity-sensor");
      viewer.entities.remove(beacons.current.humidity);
      beacons.current.humidity = null;
    }
    if (!layers.humidity || !humidity) return;
    const id = "humidity-sensor";
    const pin = groundPinOpts("#7a8f9c", 18);
    beacons.current.humidity = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(
        humidity.lon + 0.0006,
        humidity.lat + 0.0004,
        2,
      ),
      ...pin,
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Humidity",
      subtitle: `${humidity.value.toFixed(0)}%`,
      details: [
        { label: "RH", value: `${humidity.value.toFixed(0)} ${humidity.unit}` },
        { label: "Source", value: humidity.source || "openweather" },
      ],
      lon: humidity.lon,
      lat: humidity.lat,
    });
  }, [humidity, layers.humidity]);

  // Precip — pin only
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.precip) {
      metaRef.current.delete("precip-sensor");
      viewer.entities.remove(beacons.current.precip);
      beacons.current.precip = null;
    }
    if (!layers.precip || !precip) return;
    const id = "precip-sensor";
    const wet = precip.value > 0.05;
    const pin = groundPinOpts(wet ? "#6a8aaa" : "#6b7280", 18);
    beacons.current.precip = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(
        precip.lon - 0.0006,
        precip.lat + 0.0005,
        2,
      ),
      ...pin,
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Precipitation",
      subtitle: `${precip.value.toFixed(2)} ${precip.unit}`,
      details: [
        { label: "1h", value: `${precip.value.toFixed(2)} ${precip.unit}` },
        { label: "Source", value: precip.source || "openweather" },
      ],
      lon: precip.lon,
      lat: precip.lat,
    });
  }, [precip, layers.precip]);

  return <div className="cesium-host" ref={containerRef} />;
}
