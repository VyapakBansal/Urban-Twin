"""Seed neighborhood_bounds from AOI bbox in settings."""

from __future__ import annotations

import asyncio

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from urban_twin.config import settings
from urban_twin.db.models import NeighborhoodBounds
from urban_twin.db.session import AsyncSessionLocal


def _bbox_polygon_wkt(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> str:
    return (
        f"POLYGON(("
        f"{min_lon} {min_lat}, "
        f"{max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, "
        f"{min_lon} {max_lat}, "
        f"{min_lon} {min_lat}"
        f"))"
    )


async def seed_aoi() -> None:
    min_lon, min_lat, max_lon, max_lat = settings.aoi_bbox
    wkt = _bbox_polygon_wkt(min_lon, min_lat, max_lon, max_lat)

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(NeighborhoodBounds).where(NeighborhoodBounds.name == settings.aoi_name)
        )
        if existing:
            existing.geometry = WKTElement(wkt, srid=4326)
            print(f"Updated AOI '{settings.aoi_name}'")
        else:
            session.add(
                NeighborhoodBounds(
                    name=settings.aoi_name,
                    geometry=WKTElement(wkt, srid=4326),
                )
            )
            print(f"Inserted AOI '{settings.aoi_name}'")
        await session.commit()


def main() -> None:
    asyncio.run(seed_aoi())


if __name__ == "__main__":
    main()
