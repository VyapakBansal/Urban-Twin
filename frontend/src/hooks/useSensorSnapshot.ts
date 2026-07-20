import { useEffect, useMemo, useState } from "react";
import type { LiveReadingEvent, Reading } from "../types";
import { readingToLive } from "../lib/readings";
import { useLiveReadings } from "./useLiveReadings";

export function useSensorSnapshot(
  seed: Record<string, Reading>,
  wsEnabled: boolean,
) {
  const { latestByType: liveByType, status: wsStatus } =
    useLiveReadings(wsEnabled);
  const [pulseKey, setPulseKey] = useState(0);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    const hit =
      liveByType.temp || liveByType.river_level || liveByType.aqi_pm25;
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

  const liveTemp = useMemo(
    () => liveByType.temp ?? readingToLive(seed.temp),
    [liveByType.temp, seed.temp],
  );
  const river = useMemo(
    () =>
      liveByType.river_level ??
      readingToLive(seed["river:river_level"] || seed.river_level),
    [liveByType.river_level, seed],
  );
  const air = useMemo(
    () =>
      liveByType.aqi_pm25 ??
      readingToLive(seed["openaq:aqi_pm25"] || seed.aqi_pm25),
    [liveByType.aqi_pm25, seed],
  );
  const wind = useMemo(
    () => liveByType.wind ?? readingToLive(seed.wind),
    [liveByType.wind, seed.wind],
  );
  const windDir = useMemo(
    () => liveByType.wind_dir ?? readingToLive(seed.wind_dir),
    [liveByType.wind_dir, seed.wind_dir],
  );
  const humidity = useMemo(
    () => liveByType.humidity ?? readingToLive(seed.humidity),
    [liveByType.humidity, seed.humidity],
  );
  const precip = useMemo(
    () => liveByType.precip ?? readingToLive(seed.precip),
    [liveByType.precip, seed.precip],
  );

  return {
    liveTemp,
    river,
    air,
    wind,
    windDir,
    humidity,
    precip,
    wsStatus,
    pulseKey,
    flash,
  };
}

export type SensorBundle = {
  liveTemp: LiveReadingEvent | null;
  river: LiveReadingEvent | null;
  air: LiveReadingEvent | null;
  wind: LiveReadingEvent | null;
  windDir: LiveReadingEvent | null;
  humidity: LiveReadingEvent | null;
  precip: LiveReadingEvent | null;
};
