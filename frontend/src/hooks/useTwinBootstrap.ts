import { useEffect, useState } from "react";
import {
  fetchAmenities,
  fetchBuildings,
  fetchForecasts,
  fetchHealth,
  fetchIncidents,
  fetchLatestReadings,
  fetchLayerCounts,
  fetchPathways,
  fetchWindGrid,
} from "../api";
import { latestReadingMap } from "../lib/readings";
import type {
  Amenity,
  Building,
  Forecast,
  Incident,
  LayerCounts,
  Pathway,
  Reading,
  WindCell,
} from "../types";

export function useTwinBootstrap() {
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [pathways, setPathways] = useState<Pathway[]>([]);
  const [amenities, setAmenities] = useState<Amenity[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [storedForecasts, setStoredForecasts] = useState<Forecast[]>([]);
  const [windGrid, setWindGrid] = useState<WindCell[]>([]);
  const [seed, setSeed] = useState<Record<string, Reading>>({});
  const [counts, setCounts] = useState<LayerCounts | null>(null);
  const [apiOk, setApiOk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        setLoading(true);
        const [health, b, readings, fcs, paths, amens, incs, lc, windCells] =
          await Promise.all([
            fetchHealth({ signal: ac.signal }),
            fetchBuildings(8000, { signal: ac.signal }),
            fetchLatestReadings({ signal: ac.signal }),
            fetchForecasts({ signal: ac.signal }),
            fetchPathways({ signal: ac.signal }),
            fetchAmenities({ signal: ac.signal }),
            fetchIncidents({ signal: ac.signal }),
            fetchLayerCounts({ signal: ac.signal }),
            fetchWindGrid({ signal: ac.signal }).catch(() => [] as WindCell[]),
          ]);
        if (ac.signal.aborted) return;
        setApiOk(health.status === "ok");
        setBuildings(b);
        setSeed(latestReadingMap(readings));
        setStoredForecasts(fcs);
        setPathways(paths);
        setAmenities(amens);
        setIncidents(incs);
        setCounts(lc);
        setWindGrid(windCells);
        setError(null);
      } catch (e) {
        if (ac.signal.aborted) return;
        if (e instanceof DOMException && e.name === "AbortError") return;
        if (e instanceof Error && /abort/i.test(e.message)) return;
        setApiOk(false);
        setError(e instanceof Error ? e.message : "Failed to load twin data");
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    })();
    return () => ac.abort();
  }, []);

  return {
    buildings,
    pathways,
    amenities,
    incidents,
    storedForecasts,
    windGrid,
    seed,
    counts,
    apiOk,
    error,
    loading,
  };
}
