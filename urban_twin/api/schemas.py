"""Pydantic response / query models for the REST API."""

from datetime import datetime

from pydantic import BaseModel, Field


class BuildingOut(BaseModel):
    id: int
    height: float | None
    source: str
    geojson: dict


class ReadingOut(BaseModel):
    id: int
    station_id: str
    reading_type: str
    value: float
    unit: str
    recorded_at: datetime
    lon: float
    lat: float


class ForecastOut(BaseModel):
    id: int
    station_id: str
    reading_type: str
    predicted_value: float
    target_time: datetime
    model_version: str
    generated_at: datetime
    lon: float
    lat: float
    notes: str | None = None


class ErrorOut(BaseModel):
    detail: str


class HealthOut(BaseModel):
    status: str = "ok"
    service: str = "urban-twin-api"


class BBoxParams(BaseModel):
    """Optional bbox filter: min_lon,min_lat,max_lon,max_lat"""

    bbox: str | None = Field(
        default=None,
        description="Comma-separated min_lon,min_lat,max_lon,max_lat",
    )

    def parsed(self) -> tuple[float, float, float, float] | None:
        if not self.bbox:
            return None
        parts = [p.strip() for p in self.bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat")
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError("bbox requires min < max for lon and lat")
        return min_lon, min_lat, max_lon, max_lat
