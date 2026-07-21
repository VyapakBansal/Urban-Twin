from datetime import datetime, timedelta, timezone

import pytest

from urban_twin.config import Settings
from urban_twin.drone.envelope import ControlGuard, ControlRejected, VehicleState
from urban_twin.messaging.schemas import DroneControlEvent


NOW = datetime(2026, 7, 21, 18, 0, tzinfo=timezone.utc)
STATE = VehicleState(north_m=0.0, east_m=0.0, down_m=-10.0, yaw_deg=0.0)


def config() -> Settings:
    return Settings(_env_file=None)


def command(sequence: int = 1, **changes) -> DroneControlEvent:
    values = {
        "client_id": "test-browser",
        "sequence": sequence,
        "issued_at": NOW,
        "command": "velocity_body",
        "forward_m_s": 2.0,
    }
    values.update(changes)
    return DroneControlEvent(**values)


def test_guard_accepts_bounded_fresh_command():
    accepted = ControlGuard(config()).validate(
        command(),
        STATE,
        now=NOW,
        monotonic_now=10.0,
    )
    assert accepted.forward_m_s == 2.0


def test_guard_rejects_stale_and_replayed_commands():
    guard = ControlGuard(config())
    with pytest.raises(ControlRejected, match="stale"):
        guard.validate(
            command(issued_at=NOW - timedelta(seconds=2)),
            STATE,
            now=NOW,
            monotonic_now=10.0,
        )

    guard.validate(command(), STATE, now=NOW, monotonic_now=10.0)
    with pytest.raises(ControlRejected, match="sequence"):
        guard.validate(command(), STATE, now=NOW, monotonic_now=11.0)


def test_guard_rejects_speed_altitude_and_geofence_violations():
    with pytest.raises(ControlRejected, match="horizontal speed"):
        ControlGuard(config()).validate(
            command(forward_m_s=6.0),
            STATE,
            now=NOW,
            monotonic_now=10.0,
        )

    near_ceiling = VehicleState(
        north_m=0.0,
        east_m=0.0,
        down_m=-119.5,
        yaw_deg=0.0,
    )
    with pytest.raises(ControlRejected, match="altitude"):
        ControlGuard(config()).validate(
            command(down_m_s=-2.0),
            near_ceiling,
            now=NOW,
            monotonic_now=10.0,
        )

    outside_north_edge = VehicleState(
        north_m=1010.0,
        east_m=0.0,
        down_m=-10.0,
        yaw_deg=0.0,
    )
    with pytest.raises(ControlRejected, match="geofence"):
        ControlGuard(config()).validate(
            command(forward_m_s=5.0),
            outside_north_edge,
            now=NOW,
            monotonic_now=10.0,
        )


def test_guard_rate_limits_velocity_commands():
    guard = ControlGuard(config())
    guard.validate(command(1), STATE, now=NOW, monotonic_now=10.0)
    with pytest.raises(ControlRejected, match="rate"):
        guard.validate(command(2), STATE, now=NOW, monotonic_now=10.01)


def test_emergency_hold_is_accepted_without_telemetry():
    hold = command(command="hold", forward_m_s=0.0)
    accepted = ControlGuard(config()).validate(
        hold,
        None,
        now=NOW,
        monotonic_now=10.0,
    )
    assert accepted.command == "hold"

