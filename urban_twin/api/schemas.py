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
    source: str = "weather"
    reading_type: str
    value: float
    unit: str
    recorded_at: datetime
    lon: float
    lat: float


class PathwayOut(BaseModel):
    id: int
    name: str | None
    source: str
    geojson: dict


class AmenityOut(BaseModel):
    id: int
    name: str | None
    amenity_type: str
    source: str
    lon: float
    lat: float


class IncidentOut(BaseModel):
    id: int
    external_id: str
    description: str | None
    started_at: datetime | None
    source: str
    lon: float
    lat: float


class LayerCountsOut(BaseModel):
    buildings: int
    pathways: int
    amenities: int
    incidents: int
    readings: int


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


class PredictOut(BaseModel):
    reading_type: str
    predicted_value: float
    unit: str
    target_time: datetime
    horizon_hours: float | None = None
    model_version: str
    notes: str | None = None
    horizons_trained: list[int] = Field(default_factory=list)


class PredictBatchOut(BaseModel):
    reading_type: str
    unit: str
    model_version: str
    horizons_trained: list[int]
    predictions: list[PredictOut]


class ModelInfoOut(BaseModel):
    reading_type: str
    model_version: str
    horizons: list[int]
    unit: str
    metrics: dict[str, dict[str, float]]


class WindCellOut(BaseModel):
    lon: float
    lat: float
    speed_ms: float
    direction_deg: float
    recorded_at: datetime
    source: str = "open-meteo"


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
