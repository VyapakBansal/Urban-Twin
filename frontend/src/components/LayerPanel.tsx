import type { LayerState } from "../types";
import { ForecastPanel } from "./ForecastPanel";
import type { Forecast } from "../types";

export type LayerRow = {
  key: keyof LayerState;
  label: string;
  meta: string;
};

type Props = {
  rows: LayerRow[];
  layers: LayerState;
  onToggle: (key: keyof LayerState) => void;
  onFly: (key: keyof LayerState) => void;
  horizon: number;
  onHorizonChange: (h: number) => void;
  forecasts: Forecast[];
  predictLoading: boolean;
  predictError: string | null;
  showPredictHint: boolean;
  error: string | null;
};

export function LayerPanel({
  rows,
  layers,
  onToggle,
  onFly,
  horizon,
  onHorizonChange,
  forecasts,
  predictLoading,
  predictError,
  showPredictHint,
  error,
}: Props) {
  return (
    <aside className="layer-panel" aria-label="Twin layers">
      <p className="panel-title">Layers</p>
      {rows.map(({ key, label, meta }) => (
        <div key={key} className="layer-row">
          <input
            type="checkbox"
            checked={layers[key]}
            onChange={() => onToggle(key)}
            aria-label={`Toggle ${label}`}
          />
          <button
            type="button"
            className="layer-fly"
            onClick={() => onFly(key)}
            title={`Fly to ${label}`}
          >
            <span className="layer-label">{label}</span>
            <span className="layer-meta">{meta}</span>
          </button>
        </div>
      ))}

      {layers.forecast && (
        <ForecastPanel
          horizon={horizon}
          onHorizonChange={onHorizonChange}
          forecasts={forecasts}
          loading={predictLoading}
          error={predictError}
          showFallbackHint={showPredictHint}
        />
      )}

      {error && <p className="error">{error}</p>}
    </aside>
  );
}
