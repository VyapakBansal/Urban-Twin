import { useEffect, useRef } from "react";
import {
  Cartesian2,
  Cartesian3,
  Color,
  ColorMaterialProperty,
  CallbackProperty,
  defined,
  EllipsoidTerrainProvider,
  Entity,
  HorizontalOrigin,
  Ion,
  LabelStyle,
  Rectangle,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  UrlTemplateImageryProvider,
  Viewer,
  VerticalOrigin,
  Math as CesiumMath,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import type {
  Amenity,
  Building,
  CameraCommand,
  Forecast,
  Incident,
  LayerState,
  LiveReadingEvent,
  MapSelection,
  Pathway,
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
  forecasts: Forecast[];
  pulseKey: number;
  selectionId: string | null;
  onSelect: (sel: MapSelection | null) => void;
  cameraCommand: CameraCommand | null;
  cameraCommandKey: number;
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

function airColor(pm25: number): Color {
  if (pm25 <= 12) return Color.fromCssColorString("#4ade80");
  if (pm25 <= 35) return Color.fromCssColorString("#fbbf24");
  if (pm25 <= 55) return Color.fromCssColorString("#fb923c");
  return Color.fromCssColorString("#ef4444");
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

export function CesiumMap({
  buildings,
  pathways,
  amenities,
  incidents,
  layers,
  liveTemp,
  river,
  air,
  forecasts,
  pulseKey,
  selectionId,
  onSelect,
  cameraCommand,
  cameraCommandKey,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const ids = useRef<Record<string, string[]>>({
    buildings: [],
    pathways: [],
    amenities: [],
    incidents: [],
  });
  const beacons = useRef<Record<string, Entity | null>>({
    live: null,
    river: null,
    air: null,
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
    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(
      new UrlTemplateImageryProvider({
        url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        credit: "© OSM © CARTO",
      }),
    );
    viewer.scene.globe.baseColor = Color.fromCssColorString("#0b0f14");
    viewer.scene.backgroundColor = Color.fromCssColorString("#0b0f14");
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
        material: Color.fromCssColorString("#d4a373").withAlpha(0.07),
        outline: true,
        outlineColor: Color.fromCssColorString("#d4a373").withAlpha(0.85),
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
    return () => {
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
      didFly.current = false;
      metaRef.current.clear();
    };
  }, []);

  // Camera commands from toolbar / layer panel
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !cameraCommand || cameraCommandKey === 0) return;
    applyCamera(viewer, cameraCommand);
  }, [cameraCommand, cameraCommandKey]);

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
        semiMajorAxis: meta.kind === "building" ? 45 : 55,
        semiMinorAxis: meta.kind === "building" ? 45 : 55,
        material: Color.fromCssColorString("#f59e0b").withAlpha(0.22),
        outline: true,
        outlineColor: Color.fromCssColorString("#f59e0b").withAlpha(0.95),
        height: 1,
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
        const selected = selectionId === id || selectionId === `bldg-${b.id}-0`;
        const c = centroid(ring);
        const h = heightForBuilding(b);
        viewer.entities.add({
          id,
          polygon: {
            hierarchy: Cartesian3.fromDegreesArray(positions),
            extrudedHeight: h,
            material: facadeColor(b, selected),
            outline: selected,
            outlineColor: Color.fromCssColorString("#fde68a"),
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
  }, [buildings, layers.buildings, selectionId]);

  // Pathways
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
      const selected = selectionId === id;
      viewer.entities.add({
        id,
        polyline: {
          positions: Cartesian3.fromDegreesArray(positions),
          width: selected ? 6 : 3,
          material: Color.fromCssColorString(selected ? "#5eead4" : "#2dd4bf").withAlpha(
            selected ? 1 : 0.85,
          ),
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
  }, [pathways, layers.pathways, selectionId]);

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
        label:
          a.amenity_type === "transit" || selected
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
        label: {
          text: selected ? inc.description?.slice(0, 40) || "Incident" : "Incident",
          font: "600 11px DM Sans, sans-serif",
          fillColor: Color.WHITE,
          pixelOffset: new Cartesian2(0, -16),
          showBackground: true,
          backgroundColor: Color.fromCssColorString("#7f1d1d").withAlpha(0.9),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
      metaRef.current.set(id, {
        kind: "incident",
        id,
        title: "Traffic incident",
        subtitle: inc.external_id,
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

  // Live weather beacon
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.live) {
      metaRef.current.delete("live-sensor");
      viewer.entities.remove(beacons.current.live);
      beacons.current.live = null;
    }
    if (!layers.live || !liveTemp) return;
    const t0 = Date.now();
    const id = "live-sensor";
    beacons.current.live = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(liveTemp.lon, liveTemp.lat, 5),
      cylinder: {
        length: 55,
        topRadius: 6,
        bottomRadius: 14,
        material: new ColorMaterialProperty(
          new CallbackProperty(() => {
            const pulse =
              0.55 + 0.35 * Math.sin((Date.now() - t0 + pulseKey * 100) / 280);
            return Color.fromCssColorString("#f59e0b").withAlpha(pulse);
          }, false),
        ),
      },
      label: {
        text: `${liveTemp.value.toFixed(1)}°C · weather`,
        font: "600 14px DM Sans, sans-serif",
        fillColor: Color.WHITE,
        style: LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Color.BLACK,
        outlineWidth: 3,
        verticalOrigin: VerticalOrigin.BOTTOM,
        horizontalOrigin: HorizontalOrigin.CENTER,
        pixelOffset: new Cartesian2(0, -40),
        showBackground: true,
        backgroundColor: Color.fromCssColorString("#111827").withAlpha(0.85),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Live weather",
      subtitle: liveTemp.station_id,
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
  }, [liveTemp, layers.live, pulseKey]);

  // River beacon
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
    beacons.current.river = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(river.lon, river.lat, 5),
      cylinder: {
        length: 45,
        topRadius: 5,
        bottomRadius: 12,
        material: Color.fromCssColorString("#38bdf8").withAlpha(0.8),
      },
      label: {
        text: `Bow River  ${river.value.toFixed(2)} ${river.unit}`,
        font: "600 13px DM Sans, sans-serif",
        fillColor: Color.WHITE,
        style: LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Color.BLACK,
        outlineWidth: 3,
        verticalOrigin: VerticalOrigin.BOTTOM,
        pixelOffset: new Cartesian2(0, -36),
        showBackground: true,
        backgroundColor: Color.fromCssColorString("#0c4a6e").withAlpha(0.92),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Bow River level",
      subtitle: river.station_id,
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

  // Air quality
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    if (beacons.current.air) {
      metaRef.current.delete("air-sensor");
      viewer.entities.remove(beacons.current.air);
      beacons.current.air = null;
    }
    if (!layers.air || !air) return;
    const c = airColor(air.value);
    const id = "air-sensor";
    beacons.current.air = viewer.entities.add({
      id,
      position: Cartesian3.fromDegrees(air.lon, air.lat, 20),
      ellipse: {
        semiMajorAxis: 280,
        semiMinorAxis: 280,
        material: c.withAlpha(0.28),
        outline: true,
        outlineColor: c.withAlpha(0.9),
        height: 20,
      },
      label: {
        text: `PM2.5  ${air.value.toFixed(1)} ${air.unit}`,
        font: "600 13px DM Sans, sans-serif",
        fillColor: Color.WHITE,
        style: LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Color.BLACK,
        outlineWidth: 3,
        verticalOrigin: VerticalOrigin.BOTTOM,
        pixelOffset: new Cartesian2(0, -28),
        showBackground: true,
        backgroundColor: Color.fromCssColorString("#14532d").withAlpha(0.9),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    metaRef.current.set(id, {
      kind: "sensor",
      id,
      title: "Air quality",
      subtitle: air.station_id,
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

  // Forecasts
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    for (const e of forecastEntities.current) {
      metaRef.current.delete(String(e.id));
      viewer.entities.remove(e);
    }
    forecastEntities.current = [];
    if (!layers.forecast || !forecasts.length) return;

    for (const fc of forecasts) {
      const isRiver = fc.reading_type === "river_level";
      const id = `forecast-${fc.reading_type}`;
      const label = isRiver
        ? `+24h river ${fc.predicted_value.toFixed(2)} m`
        : `+24h ${fc.predicted_value.toFixed(1)}°C`;
      const color = isRiver ? "#38bdf8" : "#c4b5fd";
      const bg = isRiver ? "#0c4a6e" : "#312e81";
      const lonOff = isRiver ? 0.002 : 0.0012;
      const latOff = isRiver ? -0.001 : -0.0004;
      const lon = fc.lon + lonOff;
      const lat = fc.lat + latOff;
      const entity = viewer.entities.add({
        id,
        position: Cartesian3.fromDegrees(lon, lat, 5),
        cylinder: {
          length: isRiver ? 28 : 40,
          topRadius: 4,
          bottomRadius: 10,
          material: Color.fromCssColorString(color).withAlpha(0.85),
        },
        label: {
          text: `${label}\n${fc.model_version}`,
          font: "600 12px DM Sans, sans-serif",
          fillColor: Color.WHITE,
          style: LabelStyle.FILL_AND_OUTLINE,
          outlineColor: Color.BLACK,
          outlineWidth: 3,
          verticalOrigin: VerticalOrigin.BOTTOM,
          pixelOffset: new Cartesian2(0, -36),
          showBackground: true,
          backgroundColor: Color.fromCssColorString(bg).withAlpha(0.9),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
      metaRef.current.set(id, {
        kind: "forecast",
        id,
        title: isRiver ? "River forecast +24h" : "Temp forecast +24h",
        subtitle: fc.model_version,
        details: [
          {
            label: "Predicted",
            value: isRiver
              ? `${fc.predicted_value.toFixed(3)} m`
              : `${fc.predicted_value.toFixed(1)} °C`,
          },
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
  }, [forecasts, layers.forecast]);

  return <div className="cesium-host" ref={containerRef} />;
}
