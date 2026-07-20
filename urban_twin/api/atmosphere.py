"""AOI atmosphere grid (wind) from Open-Meteo — for Cesium vector layers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from urban_twin.config import settings

logger = logging.getLogger(__name__)


async def fetch_wind_grid(
    *,
    cols: int = 5,
    rows: int = 4,
) -> list[dict]:
    """Sample wind speed/direction across the AOI bbox (Open-Meteo, no key)."""
    min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
    points: list[tuple[float, float]] = []
    for i in range(rows):
        lat = min_lat + (max_lat - min_lat) * (i / max(rows - 1, 1))
        for j in range(cols):
            lon = min_lon + (max_lon - min_lon) * (j / max(cols - 1, 1))
            points.append((lon, lat))

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [_one_point(client, lon, lat) for lon, lat in points]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    out: list[dict] = []
    for (lon, lat), res in zip(points, results, strict=True):
        if isinstance(res, Exception):
            logger.warning("wind grid point failed %.4f,%.4f: %s", lon, lat, res)
            continue
        if res:
            out.append(res)
    return out


async def _one_point(
    client: httpx.AsyncClient,
    lon: float,
    lat: float,
) -> dict | None:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    r = await client.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    cur = data.get("current") or {}
    speed = cur.get("wind_speed_10m")
    direction = cur.get("wind_direction_10m")
    if speed is None or direction is None:
        return None
    t = cur.get("time")
    recorded = (
        datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone(timezone.utc)
        if t
        else datetime.now(timezone.utc)
    )
    return {
        "lon": lon,
        "lat": lat,
        "speed_ms": float(speed),
        "direction_deg": float(direction),
        "recorded_at": recorded,
        "source": "open-meteo",
    }
