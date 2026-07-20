"""City pathways near AOI — prefer OSM foot/cycle ways (Open Calgary pathway feed is sparse)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from urban_twin.config import settings
from urban_twin.db.models import Pathway
from urban_twin.ingestion.sources.amenities import _overpass

logger = logging.getLogger(__name__)


class CalgaryPathwaysSource:
    """Named Calgary for civic branding; geometry sourced from OSM paths in AOI."""

    name = "pathways"

    async def sync(self, session: AsyncSession) -> int:
        min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
        query = (
            f'[out:json][timeout:90];'
            f'('
            f'way["highway"="footway"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["highway"="cycleway"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["highway"="path"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f'way["leisure"="park"]({min_lat},{min_lon},{max_lat},{max_lon});'
            f');'
            f'out body;'
            f'>;'
            f'out skel qt;'
        )
        payload = await _overpass(query)
        nodes: dict[int, tuple[float, float]] = {}
        ways: list[dict[str, Any]] = []
        for el in payload.get("elements") or []:
            if el["type"] == "node":
                nodes[el["id"]] = (el["lon"], el["lat"])
            elif el["type"] == "way":
                ways.append(el)

        await session.execute(delete(Pathway))
        added = 0
        for way in ways:
            tags = way.get("tags") or {}
            ring: list[tuple[float, float]] = []
            for nid in way.get("nodes") or []:
                if nid not in nodes:
                    ring = []
                    break
                ring.append(nodes[nid])
            if len(ring) < 2:
                continue
            wkt = "LINESTRING(" + ", ".join(f"{lon} {lat}" for lon, lat in ring) + ")"
            name = tags.get("name") or tags.get("highway") or "pathway"
            session.add(
                Pathway(
                    name=str(name)[:256],
                    geometry=WKTElement(wkt, srid=4326),
                    source="osm",
                )
            )
            added += 1
            if added >= 1200:
                break
        await session.commit()
        logger.info("synced %s pathways (OSM foot/cycle/path)", added)
        return added
