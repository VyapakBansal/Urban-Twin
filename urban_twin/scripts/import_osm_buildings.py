"""Import OSM building footprints for the AOI into PostGIS.

Uses the Overpass API (read-only OSM query service). No API key required.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func, select, text

from urban_twin.config import settings
from urban_twin.db.models import Building
from urban_twin.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Primary + mirrors. overpass-api.de often returns 406 without a real User-Agent
# or when the instance is overloaded — try the next mirror.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

# Overpass etiquette: identify the app (generic httpx UA gets rejected).
OVERPASS_HEADERS = {
    "User-Agent": "UrbanTwin/0.1 (portfolio project; local OSM building import)",
    "Accept": "application/json",
}


def _overpass_query(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    # Overpass bbox order: south, west, north, east
    return (
        f'[out:json][timeout:90];'
        f'('
        f'way["building"]({min_lat},{min_lon},{max_lat},{max_lon});'
        f'relation["building"]({min_lat},{min_lon},{max_lat},{max_lon});'
        f');'
        f'out body;'
        f'>;'
        f'out skel qt;'
    )


def _parse_height(tags: dict[str, Any]) -> float | None:
    """Best-effort height in meters from OSM tags."""
    if "height" in tags:
        raw = str(tags["height"]).lower().replace("m", "").strip()
        try:
            return float(raw.split()[0])
        except ValueError:
            pass
    if "building:levels" in tags:
        try:
            levels = float(str(tags["building:levels"]).split(";")[0])
            return levels * 3.0  # ~3m per storey estimate
        except ValueError:
            pass
    return None


def _ring_to_wkt(nodes: list[tuple[float, float]]) -> str | None:
    if len(nodes) < 3:
        return None
    # Close the ring if needed
    if nodes[0] != nodes[-1]:
        nodes = [*nodes, nodes[0]]
    if len(nodes) < 4:
        return None
    coords = ", ".join(f"{lon} {lat}" for lon, lat in nodes)
    return f"POLYGON(({coords}))"


def elements_to_building_wkts(payload: dict[str, Any]) -> list[tuple[str, float | None]]:
    """Convert Overpass JSON → list of (polygon WKT, height_m)."""
    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, dict[str, Any]] = {}

    for el in payload.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif el["type"] == "way":
            ways[el["id"]] = el

    buildings: list[tuple[str, float | None]] = []
    for way in ways.values():
        tags = way.get("tags") or {}
        if "building" not in tags:
            continue
        ring: list[tuple[float, float]] = []
        for nid in way.get("nodes", []):
            if nid not in nodes:
                ring = []
                break
            ring.append(nodes[nid])
        wkt = _ring_to_wkt(ring)
        if wkt is None:
            continue
        buildings.append((wkt, _parse_height(tags)))
    return buildings


async def fetch_osm_buildings() -> list[tuple[str, float | None]]:
    min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
    query = _overpass_query(min_lat, min_lon, max_lat, max_lon)
    logger.info(
        "querying Overpass for buildings in bbox (%.4f,%.4f)-(%.4f,%.4f)",
        min_lon,
        min_lat,
        max_lon,
        max_lat,
    )

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=120.0, headers=OVERPASS_HEADERS) as client:
        for url in OVERPASS_ENDPOINTS:
            try:
                logger.info("POST %s", url)
                response = await client.post(url, data={"data": query})
                if response.status_code >= 400:
                    logger.warning(
                        "%s returned %s: %s",
                        url,
                        response.status_code,
                        response.text[:300],
                    )
                    response.raise_for_status()
                payload = response.json()
                return elements_to_building_wkts(payload)
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning("Overpass endpoint failed (%s): %s", url, exc)
                continue

    raise RuntimeError("All Overpass endpoints failed") from last_error


async def import_buildings(*, replace: bool = True) -> int:
    buildings = await fetch_osm_buildings()
    if not buildings:
        logger.warning("Overpass returned 0 building polygons")
        return 0

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        # Ensure PostGIS is available (already is, but cheap sanity check)
        await session.execute(text("SELECT PostGIS_Version()"))

        if replace:
            await session.execute(delete(Building))

        for wkt, height in buildings:
            session.add(
                Building(
                    geometry=WKTElement(wkt, srid=4326),
                    height=height,
                    source="OSM",
                    imported_at=now,
                )
            )
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Building))
    return int(count or 0)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    count = asyncio.run(import_buildings(replace=True))
    print(f"Imported {count} OSM buildings for AOI '{settings.aoi_name}'")


if __name__ == "__main__":
    main()
