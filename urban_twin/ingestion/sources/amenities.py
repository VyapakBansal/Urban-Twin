"""OSM amenities (cafes, parks, CTrain) via Overpass for AOI."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from urban_twin.config import settings
from urban_twin.db.models import Amenity

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
HEADERS = {
    "User-Agent": "UrbanTwin/0.5 (portfolio; OSM amenities)",
    "Accept": "application/json",
}


class AmenitiesSource:
    name = "amenities"

    async def sync(self, session: AsyncSession) -> int:
        min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
        query = (
            f'[out:json][timeout:90];'
            f'('
            f'node["amenity"="cafe"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["amenity"="restaurant"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["leisure"="park"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["station"="subway"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'node["public_transport"="station"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f');out body;'
        )
        payload = await _overpass(query)
        elements = payload.get("elements") or []

        await session.execute(delete(Amenity))
        added = 0
        for el in elements:
            if el.get("type") != "node":
                continue
            lon = el.get("lon")
            lat = el.get("lat")
            if lon is None or lat is None:
                continue
            tags = el.get("tags") or {}
            amenity_type = _classify(tags)
            name = tags.get("name")
            session.add(
                Amenity(
                    name=str(name)[:256] if name else None,
                    amenity_type=amenity_type,
                    geometry=WKTElement(f"POINT({lon} {lat})", srid=4326),
                    source="osm",
                )
            )
            added += 1
        await session.commit()
        logger.info("synced %s OSM amenities", added)
        return added


def _classify(tags: dict[str, Any]) -> str:
    if tags.get("railway") == "station" or tags.get("station") == "subway":
        return "transit"
    if tags.get("public_transport") == "station":
        return "transit"
    if tags.get("leisure") == "park":
        return "park"
    if tags.get("amenity") == "cafe":
        return "cafe"
    if tags.get("amenity") == "restaurant":
        return "restaurant"
    return tags.get("amenity") or tags.get("leisure") or "poi"


async def _overpass(query: str) -> dict[str, Any]:
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=120.0, headers=HEADERS) as client:
        for url in OVERPASS_ENDPOINTS:
            try:
                resp = await client.post(url, data={"data": query})
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last = exc
                logger.warning("Overpass %s failed: %s", url, exc)
    raise RuntimeError("All Overpass endpoints failed") from last
