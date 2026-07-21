from datetime import datetime, timezone

from urban_twin.config import Settings
from urban_twin.drone.bridge import TelemetrySnapshot, build_telemetry_event
from urban_twin.messaging.schemas import DroneControlEvent, DroneTelemetryEvent


def test_snapshot_maps_to_typed_drone_event():
    config = Settings(
        _env_file=None,
        drone_home_lat=51.053,
        drone_home_lon=-114.081,
        drone_home_alt_m=1045.0,
    )
    snapshot = TelemetrySnapshot(
        north_m=10.0,
        east_m=-4.0,
        down_m=-12.0,
        velocity_north_m_s=1.0,
        velocity_east_m_s=0.5,
        velocity_down_m_s=-0.2,
        roll_deg=2.0,
        pitch_deg=-3.0,
        yaw_deg=-10.0,
        armed=True,
        flight_mode="OFFBOARD",
        has_position=True,
        has_attitude=True,
    )
    recorded_at = datetime(2026, 7, 21, tzinfo=timezone.utc)

    event = build_telemetry_event(
        snapshot,
        config,
        sequence=7,
        recorded_at=recorded_at,
    )

    assert isinstance(event, DroneTelemetryEvent)
    assert event.sequence == 7
    assert event.relative_altitude_m == 12.0
    assert event.altitude_m == 1057.0
    assert event.yaw_deg == 350.0
    assert event.armed is True
    assert event.flight_mode == "OFFBOARD"


def test_drone_control_round_trip_schema():
    event = DroneControlEvent(
        client_id="browser-a",
        sequence=1,
        issued_at=datetime.now(timezone.utc),
        command="velocity_body",
        forward_m_s=2.0,
        down_m_s=-0.5,
        yaw_rate_deg_s=30.0,
    )
    restored = DroneControlEvent.model_validate_json(event.model_dump_json())
    assert restored == event

