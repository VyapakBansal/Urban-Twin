import { useEffect, useRef } from "react";
import type {
  DroneCameraMode,
  DroneControlCommand,
  DroneTelemetryEvent,
} from "../types";

type SendControl = (
  command: DroneControlCommand["command"],
  values?: Partial<
    Pick<
      DroneControlCommand,
      "forward_m_s" | "right_m_s" | "down_m_s" | "yaw_rate_deg_s"
    >
  >,
) => boolean;

type Props = {
  visible: boolean;
  phone: boolean;
  status: string;
  telemetry: DroneTelemetryEvent | null;
  controlError: string | null;
  cameraMode: DroneCameraMode;
  onCameraMode: (mode: DroneCameraMode) => void;
  sendControl: SendControl;
};

const MOVE_SPEED = 2.0;
const CLIMB_SPEED = 0.5;

function droneStatusLabel(status: string, telemetry: DroneTelemetryEvent | null, stale: boolean): string {
  if (status === "open" && (!telemetry || stale)) {
    return "waiting for PX4";
  }
  if (status === "connecting") return "connecting…";
  if (status === "closed") return "reconnecting…";
  if (status === "error") return "bridge error";
  if (status === "disabled") return "off";
  return status;
}

export function DroneControls({
  visible,
  phone,
  status,
  telemetry,
  controlError,
  cameraMode,
  onCameraMode,
  sendControl,
}: Props) {
  const sendRef = useRef(sendControl);
  sendRef.current = sendControl;

  const connected = status === "open";
  const stale = telemetry
    ? Date.now() - new Date(telemetry.recorded_at).getTime() > 1500
    : true;
  const px4Live = connected && Boolean(telemetry) && !stale;
  const controllable = px4Live && !phone;
  // WASDQE is live as soon as the vehicle is armed; Arm/Take off still come first.
  const wasdqeEnabled = controllable && Boolean(telemetry?.armed);

  useEffect(() => {
    if (!visible || !wasdqeEnabled) return;
    const pressed = new Set<string>();
    let inputWasActive = false;

    const mapKey = (event: KeyboardEvent): string | null => {
      const key = event.key.toLowerCase();
      if (["w", "a", "s", "d", "q", "e"].includes(key)) return key;
      if (event.code === "ArrowUp") return "w";
      if (event.code === "ArrowDown") return "s";
      if (event.code === "ArrowLeft") return "a";
      if (event.code === "ArrowRight") return "d";
      return null;
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      const key = mapKey(event);
      if (!key) return;
      pressed.add(key);
      event.preventDefault();
    };
    const onKeyUp = (event: KeyboardEvent) => {
      const key = mapKey(event);
      if (!key) return;
      if (pressed.delete(key)) event.preventDefault();
    };
    const onBlur = () => pressed.clear();

    // 10 Hz browser stream; bridge still enforces envelope + stale hold.
    const timer = window.setInterval(() => {
      const active = pressed.size > 0;
      if (!active && !inputWasActive) return;
      if (!active) {
        sendRef.current("hold");
        inputWasActive = false;
        return;
      }
      inputWasActive = true;
      sendRef.current("velocity_body", {
        forward_m_s:
          MOVE_SPEED * (Number(pressed.has("w")) - Number(pressed.has("s"))),
        right_m_s:
          MOVE_SPEED * (Number(pressed.has("d")) - Number(pressed.has("a"))),
        // Body-frame FRD: negative down = climb.
        down_m_s:
          CLIMB_SPEED * (Number(pressed.has("e")) - Number(pressed.has("q"))),
        yaw_rate_deg_s: 0,
      });
    }, 100);

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
      if (inputWasActive) sendRef.current("hold");
    };
  }, [visible, wasdqeEnabled]);

  if (!visible) return null;

  return (
    <section className="drone-controls" aria-label="Drone controls">
      <div className="drone-controls-head">
        <div>
          <p className="panel-title">Drone</p>
          <strong className={px4Live ? "ok" : "bad"}>
            {px4Live ? telemetry!.flight_mode : droneStatusLabel(status, telemetry, stale)}
          </strong>
        </div>
        {telemetry && (
          <span className="drone-altitude">
            {telemetry.relative_altitude_m.toFixed(1)} m AGL
          </span>
        )}
      </div>

      {!phone ? (
        <>
          <div className="drone-actions">
            <button
              type="button"
              disabled={!controllable || telemetry?.armed}
              onClick={() => sendControl("arm")}
            >
              Arm
            </button>
            <button
              type="button"
              disabled={!controllable || !telemetry?.armed}
              onClick={() => sendControl("takeoff")}
            >
              Take off
            </button>
            <button
              type="button"
              className="is-danger"
              disabled={!controllable || !telemetry?.armed}
              onClick={() => sendControl("land")}
            >
              Land
            </button>
          </div>
          <p className="drone-key-hint">
            {wasdqeEnabled
              ? "WASD move · Q up · E down"
              : !connected
                ? "Drone link reconnecting…"
                : stale
                  ? "Telemetry paused — check npm run drone"
                  : "Arm + Take off, then WASD / QE"}
          </p>
        </>
      ) : (
        <p className="drone-key-hint">Flight controls are desktop-only.</p>
      )}

      <div className="drone-camera-modes" aria-label="Drone camera mode">
        {(["free", "follow", "fpv"] as const).map((mode) => (
          <button
            type="button"
            key={mode}
            className={cameraMode === mode ? "is-active" : ""}
            disabled={!telemetry && mode !== "free"}
            onClick={() => onCameraMode(mode)}
          >
            {mode}
          </button>
        ))}
      </div>
      {controlError && <p className="error">{controlError}</p>}
    </section>
  );
}
