from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from urban_twin.db.models import ReadingType


class NormalizedReading(BaseModel):
    station_id: str
    lon: float
    lat: float
    reading_type: ReadingType
    value: float
    unit: str
    recorded_at: datetime
    source: str = "weather"

    @field_validator("recorded_at")
    @classmethod
    def ensure_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("value")
    @classmethod
    def finite_value(cls, v: float) -> float:
        if v != v:  # NaN
            raise ValueError("value must be a finite number")
        return v


# OpenWeather Current Weather units when units=metric
READING_SPECS: dict[ReadingType, tuple[str, Any]] = {
    ReadingType.TEMP: ("C", ("main", "temp")),
    ReadingType.HUMIDITY: ("%", ("main", "humidity")),
    ReadingType.WIND: ("m/s", ("wind", "speed")),
    ReadingType.PRECIP: ("mm", None),  # special: rain.1h or snow.1h or 0
}


def _dig(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = payload
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def normalize_openweather_current(
    payload: dict[str, Any],
    *,
    station_id: str,
    lon: float,
    lat: float,
) -> list[NormalizedReading]:
    """Map OpenWeather Current Weather JSON → validated readings."""
    if "dt" not in payload:
        raise ValueError("OpenWeather payload missing dt")

    recorded_at = datetime.fromtimestamp(int(payload["dt"]), tz=timezone.utc)
    readings: list[NormalizedReading] = []

    for reading_type, (unit, path) in READING_SPECS.items():
        if reading_type == ReadingType.PRECIP:
            rain = _dig(payload, ("rain", "1h"))
            snow = _dig(payload, ("snow", "1h"))
            value = float(rain or snow or 0.0)
        else:
            assert path is not None
            raw = _dig(payload, path)
            if raw is None:
                raise ValueError(f"missing field for {reading_type}: {'.'.join(path)}")
            value = float(raw)

        readings.append(
            NormalizedReading(
                station_id=station_id,
                lon=lon,
                lat=lat,
                reading_type=reading_type,
                value=value,
                unit=unit,
                recorded_at=recorded_at,
                source="weather",
            )
        )

    return readings
