"""Kafka message shapes shared by producers and consumers."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from urban_twin.db.models import ReadingType


class ReadingEvent(BaseModel):
    """Payload published to sensor.readings (and later pushed over WebSocket)."""

    station_id: str
    lon: float
    lat: float
    reading_type: ReadingType | str
    value: float
    unit: str
    recorded_at: datetime
    source: str = "weather"
    reading_id: int | None = Field(
        default=None,
        description="PostGIS sensor_readings.id after persist",
    )


class DroneTelemetryEvent(BaseModel):
    """Latest PX4 state published to drone.telemetry and /ws/drone."""

    event_type: Literal["drone.telemetry"] = "drone.telemetry"
    drone_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=0)
    recorded_at: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    altitude_m: float
    relative_altitude_m: float
    north_m: float
    east_m: float
    down_m: float
    velocity_north_m_s: float
    velocity_east_m_s: float
    velocity_down_m_s: float
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    armed: bool
    flight_mode: str
    source: str = "px4-mavsdk"


class DroneControlEvent(BaseModel):
    """Bounded browser command published to drone.control."""

    event_type: Literal["drone.control"] = "drone.control"
    client_id: str = Field(min_length=1, max_length=64)
    sequence: int = Field(ge=0)
    issued_at: datetime
    command: Literal["arm", "takeoff", "land", "disarm", "velocity_body", "hold"]
    forward_m_s: float = Field(default=0.0, ge=-20.0, le=20.0)
    right_m_s: float = Field(default=0.0, ge=-20.0, le=20.0)
    down_m_s: float = Field(default=0.0, ge=-10.0, le=10.0)
    yaw_rate_deg_s: float = Field(default=0.0, ge=-180.0, le=180.0)
    ttl_ms: int = Field(default=500, ge=100, le=2000)
