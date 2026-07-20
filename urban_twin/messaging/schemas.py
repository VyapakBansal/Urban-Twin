"""Kafka message shapes shared by producers and consumers."""

from datetime import datetime

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
