"""On-demand prediction helpers for the /predict REST API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from urban_twin.config import settings
from urban_twin.db.models import SensorReading
from urban_twin.db.session import AsyncSessionLocal
from urban_twin.forecast.history import (
    fetch_ec_river_levels,
    fetch_open_meteo_pm25,
    fetch_open_meteo_temps,
)
from urban_twin.forecast.lightgbm_model import MultiHorizonBundle, load_multi_bundle
from urban_twin.forecast.models import ForecastResult

logger = logging.getLogger(__name__)

UNITS = {
    "temp": "C",
    "river_level": "m",
    "aqi_pm25": "ug/m3",
}


def station_for(reading_type: str) -> str:
    if reading_type == "river_level":
        return f"bow-{settings.river_station_id}"
    if reading_type == "aqi_pm25":
        return settings.station_id
    return settings.station_id


async def load_live_series(reading_type: str) -> tuple[list[float], list]:
    station_id = station_for(reading_type)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(SensorReading.value, SensorReading.recorded_at)
            .where(SensorReading.station_id == station_id)
            .where(SensorReading.reading_type == reading_type)
            .order_by(SensorReading.recorded_at.asc())
        )
        rows = (await session.execute(stmt)).all()
    return [float(r.value) for r in rows], [r.recorded_at for r in rows]


async def series_for_predict(reading_type: str) -> tuple[list[float], list]:
    """Archive context + live points so lag features are available."""
    live_v, live_t = await load_live_series(reading_type)
    if reading_type == "temp":
        hist_v, hist_t = await fetch_open_meteo_temps(days=60)
    elif reading_type == "river_level":
        hist_v, hist_t = await fetch_ec_river_levels(days=120)
    elif reading_type == "aqi_pm25":
        hist_v, hist_t = await fetch_open_meteo_pm25(days=60)
    else:
        return live_v, live_t

    by_hour: dict = {}
    for v, t in zip(hist_v, hist_t, strict=True):
        key = t.replace(minute=0, second=0, microsecond=0)
        by_hour[key] = float(v)
    for v, t in zip(live_v, live_t, strict=True):
        if getattr(t, "tzinfo", None) is None:
            t = t.replace(tzinfo=timezone.utc)
        key = t.replace(minute=0, second=0, microsecond=0)
        by_hour[key] = float(v)
    ordered = sorted(by_hour.items(), key=lambda x: x[0])
    return [v for _, v in ordered], [t for t, _ in ordered]


def require_bundle(reading_type: str) -> MultiHorizonBundle:
    bundle = load_multi_bundle(reading_type)
    if bundle is None:
        raise FileNotFoundError(
            f"No multi-horizon model for '{reading_type}'. "
            f"Train with: python -m urban_twin.forecast.train --targets {reading_type}"
        )
    return bundle


def result_to_dict(result: ForecastResult, reading_type: str) -> dict:
    return {
        "reading_type": reading_type,
        "predicted_value": result.predicted_value,
        "unit": UNITS.get(reading_type, ""),
        "target_time": result.target_time,
        "model_version": result.model_version,
        "notes": result.notes,
        "horizons_trained": None,  # filled by caller
    }
