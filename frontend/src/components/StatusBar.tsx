type Props = {
  apiOk: boolean;
  wsStatus: string;
  buildingCount: number;
  civicCount: number;
  flash: boolean;
};

export function StatusBar({
  apiOk,
  wsStatus,
  buildingCount,
  civicCount,
  flash,
}: Props) {
  return (
    <footer className="status-bar">
      <span className={apiOk ? "ok" : "bad"}>API</span>
      <span className={wsStatus === "open" ? "ok" : "bad"}>WS</span>
      <span className="status-counts">
        {buildingCount} bld · {civicCount} civic
      </span>
      {flash && <span className="flash-pill">live</span>}
      <span className="hint">Tap to inspect · pinch zoom</span>
    </footer>
  );
}
