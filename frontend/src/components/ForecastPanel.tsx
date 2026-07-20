import { HORIZONS } from "../lib/constants";
import { forecastLabel, formatForecastMeta } from "../lib/readings";
import type { Forecast } from "../types";

type Props = {
  horizon: number;
  onHorizonChange: (h: number) => void;
  forecasts: Forecast[];
  loading: boolean;
  error: string | null;
  showFallbackHint: boolean;
};

export function ForecastPanel({
  horizon,
  onHorizonChange,
  forecasts,
  loading,
  error,
  showFallbackHint,
}: Props) {
  return (
    <div className="forecast-block">
      <p className="panel-title">Horizon</p>
      <div className="horizon-chips" role="group" aria-label="Forecast horizon">
        {HORIZONS.map((h) => (
          <button
            key={h}
            type="button"
            className={h === horizon ? "is-active" : undefined}
            onClick={() => onHorizonChange(h)}
          >
            {h}h
          </button>
        ))}
      </div>
      <ul className="forecast-list">
        {loading && <li className="muted">Loading…</li>}
        {!loading &&
          forecasts.map((f) => (
            <li key={f.reading_type}>
              <span>{forecastLabel(f.reading_type)}</span>
              <strong>{formatForecastMeta(f)}</strong>
            </li>
          ))}
        {showFallbackHint && error && <li className="muted">{error}</li>}
      </ul>
    </div>
  );
}
