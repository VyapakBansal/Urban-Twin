"""Server-side flight envelope for browser-originated commands."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from urban_twin.config import Settings
from urban_twin.drone.transform import ned_to_wgs84
from urban_twin.messaging.schemas import DroneControlEvent


class ControlRejected(ValueError):
    """A command failed a safety or freshness check."""


@dataclass(frozen=True)
class VehicleState:
    north_m: float
    east_m: float
    down_m: float
    yaw_deg: float


class ControlGuard:
    """Validate rate, freshness, sequence, speed, altitude and geofence."""

    def __init__(self, config: Settings) -> None:
        self.config = config
        self._last_sequence: dict[str, int] = {}
        self._last_velocity_at = 0.0

    def validate(
        self,
        event: DroneControlEvent,
        state: VehicleState | None,
        *,
        now: datetime | None = None,
        monotonic_now: float | None = None,
    ) -> DroneControlEvent:
        now = now or datetime.now(timezone.utc)
        monotonic_now = monotonic_now if monotonic_now is not None else time.monotonic()
        if event.issued_at.tzinfo is None:
            raise ControlRejected("issued_at must include a timezone")
        age_ms = (now - event.issued_at.astimezone(timezone.utc)).total_seconds() * 1000
        max_age_ms = min(
            event.ttl_ms,
            int(self.config.drone_command_timeout_sec * 1000),
        )
        if age_ms < -1000 or age_ms > max_age_ms:
            raise ControlRejected("command is stale or has an invalid timestamp")

        previous = self._last_sequence.get(event.client_id, -1)
        if event.sequence <= previous:
            raise ControlRejected("command sequence must increase")

        if event.command == "velocity_body":
            minimum_interval = 1.0 / self.config.drone_control_hz
            if monotonic_now - self._last_velocity_at < minimum_interval * 0.8:
                raise ControlRejected("command rate exceeds the configured limit")
            self._validate_velocity(event, state)
            self._last_velocity_at = monotonic_now

        self._last_sequence[event.client_id] = event.sequence
        return event

    def _validate_velocity(
        self,
        event: DroneControlEvent,
        state: VehicleState | None,
    ) -> None:
        if state is None:
            raise ControlRejected("vehicle telemetry is not ready")
        horizontal_speed = math.hypot(event.forward_m_s, event.right_m_s)
        if horizontal_speed > self.config.drone_max_horizontal_speed_m_s:
            raise ControlRejected("horizontal speed exceeds the flight envelope")
        if abs(event.down_m_s) > self.config.drone_max_vertical_speed_m_s:
            raise ControlRejected("vertical speed exceeds the flight envelope")
        if abs(event.yaw_rate_deg_s) > self.config.drone_max_yaw_rate_deg_s:
            raise ControlRejected("yaw rate exceeds the flight envelope")

        lookahead_sec = max(self.config.drone_command_timeout_sec, 0.5)
        yaw = math.radians(state.yaw_deg)
        north_velocity = (
            event.forward_m_s * math.cos(yaw)
            - event.right_m_s * math.sin(yaw)
        )
        east_velocity = (
            event.forward_m_s * math.sin(yaw)
            + event.right_m_s * math.cos(yaw)
        )
        predicted_down = state.down_m + event.down_m_s * lookahead_sec
        predicted_altitude = -predicted_down
        if not (
            self.config.drone_min_altitude_m
            <= predicted_altitude
            <= self.config.drone_max_altitude_m
        ):
            raise ControlRejected("command would cross the altitude envelope")

        predicted = ned_to_wgs84(
            state.north_m + north_velocity * lookahead_sec,
            state.east_m + east_velocity * lookahead_sec,
            predicted_down,
            home_lat=self.config.drone_home_lat,
            home_lon=self.config.drone_home_lon,
            home_altitude_m=self.config.drone_home_alt_m,
        )
        if not (
            self.config.aoi_min_lat <= predicted.lat <= self.config.aoi_max_lat
            and self.config.aoi_min_lon <= predicted.lon <= self.config.aoi_max_lon
        ):
            raise ControlRejected("command would cross the AOI geofence")

