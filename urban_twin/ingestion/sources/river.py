"""Bow River hydrometric levels — Environment Canada GeoMet (station 05BH004)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from urban_twin.config import settings
from urban_twin.db.models import ReadingType
from urban_twin.ingestion.normalize import NormalizedReading

logger = logging.getLogger(__name__)

GEOMET_URL = "https://api.weather.gc.ca/collections/hydrometric-realtime/items"
# Approximate station coordinates for Bow River at Calgary
BOW_LON = -114.0514
BOW_LAT = 51.05


class RiverSource:
    name = "river"

    async def fetch_readings(self) -> list[NormalizedReading]:
        station = settings.river_station_id
        headers = {"User-Agent": "UrbanTwin/0.5 (portfolio; hydrometric ingest)"}
        params = {
            "f": "json",
            "limit": 20,
            "STATION_NUMBER": station,
        }
        async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
            resp = await client.get(GEOMET_URL, params=params)
            if resp.status_code >= 400:
                # bbox fallback around Calgary
                resp = await client.get(
                    GEOMET_URL,
                    params={
                        "f": "json",
                        "limit": 100,
                        "bbox": "-114.15,50.95,-113.95,51.15",
                    },
                )
            resp.raise_for_status()
            payload = resp.json()

        features = payload.get("features") or []
        matched = [
            f
            for f in features
            if str((f.get("properties") or {}).get("STATION_NUMBER", "")).upper()
            == station.upper()
        ] or features

        if not matched:
            raise ValueError(f"No hydrometric features for {station}")

        feat = matched[0]
        props: dict[str, Any] = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or [BOW_LON, BOW_LAT]
        lon = float(coords[0])
        lat = float(coords[1])

        level = _first(props, ("LEVEL", "level", "WATER_LEVEL", "Value", "value"))
        flow = _first(props, ("DISCHARGE", "discharge", "FLOW", "flow"))
        recorded_at = _parse_ts(
            _first(props, ("DATETIME", "datetime", "DATE", "OBS_DATE", "time"))
        )

        # Some GeoMet payloads nest latest observation differently
        if level is None and "observations" in props:
            obs = props["observations"]
            if isinstance(obs, list) and obs:
                level = obs[0].get("level") or obs[0].get("value")

        out: list[NormalizedReading] = []
        if level is not None:
            out.append(
                NormalizedReading(
                    station_id=f"bow-{station}",
                    lon=lon,
                    lat=lat,
                    reading_type=ReadingType.RIVER_LEVEL,
                    value=float(level),
                    unit="m",
                    recorded_at=recorded_at,
                    source="river",
                )
            )
        if flow is not None:
            out.append(
                NormalizedReading(
                    station_id=f"bow-{station}",
                    lon=lon,
                    lat=lat,
                    reading_type=ReadingType.RIVER_FLOW,
                    value=float(flow),
                    unit="m3/s",
                    recorded_at=recorded_at,
                    source="river",
                )
            )

        if not out:
            # Still emit a placeholder-ish informative failure with props keys for logs
            raise ValueError(
                f"Hydrometric feature missing level/flow; props={list(props.keys())[:20]}"
            )
        return out


def _first(props: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in props and props[k] is not None:
            return props[k]
    # case-insensitive
    lower = {str(k).lower(): v for k, v in props.items()}
    for k in keys:
        if k.lower() in lower and lower[k.lower()] is not None:
            return lower[k.lower()]
    return None


def _parse_ts(raw: Any) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    text = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
