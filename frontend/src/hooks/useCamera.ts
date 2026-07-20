import { useCallback, useState } from "react";
import type { CameraCommand } from "../types";

export function useCamera() {
  const [cameraCommand, setCameraCommand] = useState<CameraCommand | null>(
    null,
  );
  const [cameraCommandKey, setCameraCommandKey] = useState(0);

  const runCamera = useCallback((cmd: CameraCommand) => {
    setCameraCommand(cmd);
    setCameraCommandKey((k) => k + 1);
  }, []);

  return { cameraCommand, cameraCommandKey, runCamera };
}
