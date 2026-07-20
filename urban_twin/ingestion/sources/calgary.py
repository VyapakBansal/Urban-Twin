"""City of Calgary Open Data — traffic incidents (AOI-clipped)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from urban_twin.config import settings
from urban_twin.db.models import Incident

logger = logging.getLogger(__name__)

INCIDENTS_URL = "https://data.calgary.ca/resource/35ra-9556.json"


def _in_aoi(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


class CalgaryIncidentsSource:
    name = "incidents"

    async def sync(self, session: AsyncSession) -> int:
        rows = await _fetch_json(INCIDENTS_URL, params={"$limit": 200, "$order": "start_dt DESC"})
        added = 0
        for row in rows:
            lon, lat = _incident_coords(row)
            if lon is None or lat is None:
                continue
            min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
            if not (
                min_lon - 0.02 <= lon <= max_lon + 0.02
                and min_lat - 0.02 <= lat <= max_lat + 0.02
            ):
                continue

            external_id = str(
                row.get("incident_info")
                or row.get("id")
                or row.get("unique_id")
                or f"{lon},{lat},{row.get('start_dt')}"
            )[:128]
            desc = row.get("incident_info") or row.get("description") or row.get("quadrant")
            started = _parse_dt(row.get("start_dt") or row.get("modified_dt"))

            existing = await session.scalar(
                select(Incident).where(Incident.external_id == external_id)
            )
            if existing:
                existing.description = str(desc) if desc else existing.description
                existing.geometry = WKTElement(f"POINT({lon} {lat})", srid=4326)
                existing.started_at = started
            else:
                session.add(
                    Incident(
                        external_id=external_id,
                        description=str(desc)[:2000] if desc else None,
                        geometry=WKTElement(f"POINT({lon} {lat})", srid=4326),
                        started_at=started,
                        source="calgary",
                    )
                )
                added += 1
        await session.commit()
        logger.info("upserted incidents; %s new near AOI", added)
        return added


async def _fetch_json(url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "UrbanTwin/0.5 (portfolio; Open Calgary)",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=90.0, headers=headers) as client:
        resp = await client.get(url, params=params or {"$limit": 2000})
        if resp.status_code >= 400:
            logger.warning("%s → %s", url, resp.status_code)
            return []
        data = resp.json()
        return data if isinstance(data, list) else []


def _incident_coords(row: dict[str, Any]) -> tuple[float | None, float | None]:
    if "longitude" in row and "latitude" in row:
        try:
            return float(row["longitude"]), float(row["latitude"])
        except (TypeError, ValueError):
            pass
    point = row.get("point") or row.get("location") or row.get("the_geom")
    if isinstance(point, dict):
        if "coordinates" in point:
            c = point["coordinates"]
            return float(c[0]), float(c[1])
        if "longitude" in point and "latitude" in point:
            return float(point["longitude"]), float(point["latitude"])
    return None, None


def _parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None
