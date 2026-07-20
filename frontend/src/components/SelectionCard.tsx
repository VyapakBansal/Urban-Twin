import { safeText } from "../lib/readings";
import type { CameraCommand, MapSelection } from "../types";

type Props = {
  selection: MapSelection;
  onClose: () => void;
  onFly: (cmd: CameraCommand) => void;
};

export function SelectionCard({ selection, onClose, onFly }: Props) {
  return (
    <aside className="select-card" aria-live="polite">
      <div className="select-head">
        <div>
          <p className="select-kind">{safeText(selection.kind, 32)}</p>
          <h2 className="select-title">{safeText(selection.title, 120)}</h2>
          {selection.subtitle && (
            <p className="select-sub">{safeText(selection.subtitle, 160)}</p>
          )}
        </div>
        <button
          type="button"
          className="select-close"
          onClick={onClose}
          aria-label="Close selection"
        >
          ✕
        </button>
      </div>
      <dl className="select-dl">
        {selection.details.map((d) => (
          <div key={d.label} className="select-row">
            <dt>{safeText(d.label, 40)}</dt>
            <dd>{safeText(d.value, 280)}</dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        className="select-fly"
        onClick={() =>
          onFly({
            type: "flyTo",
            lon: selection.lon,
            lat: selection.lat,
            height: selection.kind === "building" ? 160 : 220,
          })
        }
      >
        Fly here
      </button>
    </aside>
  );
}
