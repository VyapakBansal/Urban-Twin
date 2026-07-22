import { useCallback, useEffect, useRef, useState } from "react";
import { DRONE_WS_URL } from "../api";
import type { DroneControlCommand, DroneTelemetryEvent } from "../types";

type DroneWsStatus = "disabled" | "connecting" | "open" | "closed" | "error";

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isDroneTelemetry(value: unknown): value is DroneTelemetryEvent {
  if (!value || typeof value !== "object") return false;
  const event = value as Record<string, unknown>;
  return (
    event.event_type === "drone.telemetry" &&
    typeof event.drone_id === "string" &&
    typeof event.recorded_at === "string" &&
    typeof event.armed === "boolean" &&
    typeof event.flight_mode === "string" &&
    [
      "sequence",
      "lat",
      "lon",
      "altitude_m",
      "relative_altitude_m",
      "north_m",
      "east_m",
      "down_m",
      "velocity_north_m_s",
      "velocity_east_m_s",
      "velocity_down_m_s",
      "roll_deg",
      "pitch_deg",
      "yaw_deg",
    ].every((key) => isFiniteNumber(event[key]))
  );
}

export function useDroneTelemetry(enabled: boolean) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const sequenceRef = useRef(0);
  const clientIdRef = useRef(
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `browser-${Math.random().toString(36).slice(2)}`,
  );
  const [status, setStatus] = useState<DroneWsStatus>(
    enabled ? "connecting" : "disabled",
  );
  const [telemetry, setTelemetry] = useState<DroneTelemetryEvent | null>(null);
  const [controlError, setControlError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus("disabled");
      setTelemetry(null);
      return;
    }
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setStatus("connecting");
      const socket = new WebSocket(DRONE_WS_URL);
      socketRef.current = socket;
      socket.onopen = () => {
        if (!disposed) setStatus("open");
      };
      socket.onmessage = (message) => {
        try {
          const value: unknown = JSON.parse(String(message.data));
          if (isDroneTelemetry(value)) {
            setTelemetry(value);
            return;
          }
          if (value && typeof value === "object") {
            const frame = value as Record<string, unknown>;
            if (frame.event_type === "drone.control.ack") {
              setControlError(null);
              return;
            }
            if (frame.event_type === "drone.control.error") {
              setControlError("Invalid control command (check browser console).");
            }
          }
        } catch {
          // Ignore malformed/non-drone frames without destabilizing the map.
        }
      };
      socket.onerror = () => {
        if (!disposed) setStatus("error");
      };
      socket.onclose = () => {
        if (socketRef.current === socket) socketRef.current = null;
        if (disposed) return;
        setStatus("closed");
        reconnectRef.current = window.setTimeout(connect, 1500);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectRef.current !== null) {
        window.clearTimeout(reconnectRef.current);
      }
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [enabled]);

  const sendControl = useCallback(
    (
      command: DroneControlCommand["command"],
      values: Partial<
        Pick<
          DroneControlCommand,
          "forward_m_s" | "right_m_s" | "down_m_s" | "yaw_rate_deg_s"
        >
      > = {},
    ): boolean => {
      const socket = socketRef.current;
      if (!enabled || !socket || socket.readyState !== WebSocket.OPEN) return false;
      const event: DroneControlCommand = {
        event_type: "drone.control",
        client_id: clientIdRef.current,
        sequence: sequenceRef.current++,
        issued_at: new Date().toISOString(),
        command,
        ttl_ms: 500,
        ...values,
      };
      socket.send(JSON.stringify(event));
      setControlError(null);
      return true;
    },
    [enabled],
  );

  return { telemetry, status, controlError, sendControl };
}

