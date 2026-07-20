import type { CameraCommand } from "../types";

type Props = {
  onCommand: (cmd: CameraCommand) => void;
};

export function CameraToolbar({ onCommand }: Props) {
  return (
    <div className="cam-toolbar" role="toolbar" aria-label="Camera">
      <button type="button" onClick={() => onCommand({ type: "home" })}>
        Home
      </button>
      <button type="button" onClick={() => onCommand({ type: "oblique" })}>
        Street
      </button>
      <button type="button" onClick={() => onCommand({ type: "top" })}>
        Top
      </button>
    </div>
  );
}
