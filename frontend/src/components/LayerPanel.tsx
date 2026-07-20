import type { Forecast, LayerState } from "../types";
import { ForecastPanel } from "./ForecastPanel";

export type LayerRow = {
  key: keyof LayerState;
  label: string;
  meta: string;
};

type Props = {
  open: boolean;
  onClose: () => void;
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
  open,
  onClose,
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
    <>
      {open && (
        <button
          type="button"
          className="sheet-scrim"
          aria-label="Close layers"
          onClick={onClose}
        />
      )}
      <aside
        className={`layer-panel ${open ? "is-open" : ""}`}
        aria-label="Twin layers"
        aria-hidden={!open}
      >
        <div className="panel-head">
          <p className="panel-title">Layers</p>
          <button
            type="button"
            className="panel-close"
            onClick={onClose}
            aria-label="Close layers panel"
          >
            ✕
          </button>
        </div>
        <div className="layer-panel-body">
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
                onClick={() => {
                  onFly(key);
                  onClose();
                }}
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
        </div>
      </aside>
    </>
  );
}
