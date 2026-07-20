import { useEffect, useMemo, useState } from "react";
import { fetchPredict } from "../api";
import { AOI_CENTER, PREDICT_TYPES } from "../lib/constants";
import type { Forecast, LiveReadingEvent, Reading } from "../types";

type Anchor = { lon: number; lat: number; station: string };

function resolveAnchor(
  liveTemp: LiveReadingEvent | null | undefined,
  seedTemp: Reading | undefined,
): Anchor {
  const t = liveTemp ?? null;
  return {
    lon: t?.lon ?? seedTemp?.lon ?? AOI_CENTER.lon,
    lat: t?.lat ?? seedTemp?.lat ?? AOI_CENTER.lat,
    station: t?.station_id ?? seedTemp?.station_id ?? "kensington",
  };
}

export function useHorizonForecasts(opts: {
  enabled: boolean;
  apiOk: boolean;
  horizon: number;
  liveTemp: LiveReadingEvent | null;
  seedTemp: Reading | undefined;
  storedForecasts: Forecast[];
}) {
  const { enabled, apiOk, horizon, liveTemp, seedTemp, storedForecasts } =
    opts;
  const [liveForecasts, setLiveForecasts] = useState<Forecast[]>([]);
  const [predictError, setPredictError] = useState<string | null>(null);
  const [predictLoading, setPredictLoading] = useState(false);

  const anchor = useMemo(
    () => resolveAnchor(liveTemp, seedTemp),
    [liveTemp, seedTemp],
  );

  useEffect(() => {
    if (!enabled || !apiOk) return;
    const ac = new AbortController();
    (async () => {
      setPredictLoading(true);
      setPredictError(null);
      try {
        const rows = await Promise.all(
          PREDICT_TYPES.map(async (rt, idx) => {
            try {
              const p = await fetchPredict(rt, horizon, { signal: ac.signal });
              const row: Forecast = {
                id: horizon * 1000 + idx,
                station_id: anchor.station,
                reading_type: p.reading_type,
                predicted_value: p.predicted_value,
                target_time: p.target_time,
                model_version: p.model_version,
                generated_at: new Date().toISOString(),
                lon: anchor.lon,
                lat: anchor.lat,
                notes: p.notes,
                horizon_hours: p.horizon_hours ?? horizon,
              };
              return row;
            } catch {
              return null;
            }
          }),
        );
        if (ac.signal.aborted) return;
        const ok = rows.filter((r): r is Forecast => Boolean(r));
        if (ok.length) {
          setLiveForecasts(ok);
          setPredictError(null);
        } else {
          setLiveForecasts([]);
          setPredictError("Train models to unlock horizons");
        }
      } catch (e) {
        if (ac.signal.aborted) return;
        setLiveForecasts([]);
        setPredictError(e instanceof Error ? e.message : "Predict failed");
      } finally {
        if (!ac.signal.aborted) setPredictLoading(false);
      }
    })();
    return () => ac.abort();
  }, [
    enabled,
    apiOk,
    horizon,
    anchor.lon,
    anchor.lat,
    anchor.station,
  ]);

  const forecasts = useMemo(() => {
    if (liveForecasts.length) return liveForecasts;
    return storedForecasts.map((f) => ({
      ...f,
      horizon_hours: f.horizon_hours ?? 24,
    }));
  }, [liveForecasts, storedForecasts]);

  return {
    forecasts,
    liveForecasts,
    predictError,
    predictLoading,
  };
}
