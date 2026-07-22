type Props = {
  apiOk: boolean;
  wsStatus: string;
  wsEnabled: boolean;
  buildingCount: number;
  civicCount: number;
  flash: boolean;
  droneStatus: string;
  droneEnabled: boolean;
};

function statusClass(
  status: string,
  enabled: boolean,
): "ok" | "bad" | "off" {
  if (!enabled || status === "idle" || status === "disabled") return "off";
  if (status === "open") return "ok";
  if (status === "connecting" || status === "closed") return "off";
  return "bad";
}

export function StatusBar({
  apiOk,
  wsStatus,
  wsEnabled,
  buildingCount,
  civicCount,
  flash,
  droneStatus,
  droneEnabled,
}: Props) {
  return (
    <footer className="status-bar">
      <span className={apiOk ? "ok" : "bad"}>API</span>
      <span className={statusClass(wsStatus, wsEnabled)}>WS</span>
      <span className={statusClass(droneStatus, droneEnabled)}>DRONE</span>
      <span className="status-counts">
        {buildingCount} bld · {civicCount} civic
      </span>
      {flash && <span className="flash-pill">live</span>}
      <span className="hint">Tap to inspect · pinch zoom</span>
    </footer>
  );
}
