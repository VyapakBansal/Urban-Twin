"""Multi-source ingestion orchestrator.

Usage:
  .venv/Scripts/python.exe -m urban_twin.ingestion.main --once
  .venv/Scripts/python.exe -m urban_twin.ingestion.main --once --sources weather,river,air
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from urban_twin.config import settings
from urban_twin.db.session import AsyncSessionLocal
from urban_twin.ingestion.persist import write_readings
from urban_twin.ingestion.sources.amenities import AmenitiesSource
from urban_twin.ingestion.sources.calgary import CalgaryIncidentsSource
from urban_twin.ingestion.sources.calgary_pathways import CalgaryPathwaysSource
from urban_twin.ingestion.sources.openaq import AirQualitySource
from urban_twin.ingestion.sources.river import RiverSource
from urban_twin.ingestion.sources.weather import WeatherSource
from urban_twin.messaging.producer import publish_readings
from urban_twin.messaging.schemas import ReadingEvent

logger = logging.getLogger(__name__)

READING_SOURCES = {
    "weather": WeatherSource,
    "river": RiverSource,
    "air": AirQualitySource,
}

LAYER_SOURCES = {
    "pathways": CalgaryPathwaysSource,
    "incidents": CalgaryIncidentsSource,
    "amenities": AmenitiesSource,
}


async def ingest_once(
    *,
    sources: list[str] | None = None,
    publish: bool = True,
) -> dict[str, int]:
    selected = sources or settings.ingest_source_list
    counts: dict[str, int] = {}

    # Scalar readings → sensor_readings + Kafka
    for name in selected:
        if name not in READING_SOURCES:
            continue
        src = READING_SOURCES[name]()
        try:
            readings = await src.fetch_readings()
            if not readings:
                counts[name] = 0
                continue
            async with AsyncSessionLocal() as session:
                rows = await write_readings(session, readings)
            counts[name] = len(rows)
            for row in rows:
                logger.info(
                    "[%s] wrote %s=%s %s (id=%s)",
                    name,
                    row.reading_type,
                    row.value,
                    row.unit,
                    row.id,
                )
            if publish:
                events = [
                    ReadingEvent(
                        station_id=row.station_id,
                        lon=float(readings[i].lon),
                        lat=float(readings[i].lat),
                        reading_type=row.reading_type,
                        value=row.value,
                        unit=row.unit,
                        recorded_at=row.recorded_at,
                        source=row.source,
                        reading_id=row.id,
                    )
                    for i, row in enumerate(rows)
                ]
                await publish_readings(events)
        except Exception:
            logger.exception("[%s] reading ingest failed", name)
            counts[name] = -1

    # Civic / static-ish layers → dedicated tables
    for name in selected:
        if name not in LAYER_SOURCES:
            continue
        src = LAYER_SOURCES[name]()
        try:
            async with AsyncSessionLocal() as session:
                n = await src.sync(session)
            counts[name] = n
        except Exception:
            logger.exception("[%s] layer sync failed", name)
            counts[name] = -1

    return counts


async def run_loop(interval_sec: int, sources: list[str] | None) -> None:
    logger.info("multi-source ingest loop every %ss sources=%s", interval_sec, sources)
    while True:
        try:
            counts = await ingest_once(sources=sources)
            logger.info("ingest cycle: %s", counts)
        except Exception:
            logger.exception("ingest cycle failed")
        await asyncio.sleep(interval_sec)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin multi-source ingestion")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-kafka", action="store_true")
    parser.add_argument(
        "--sources",
        default=None,
        help="Comma list: weather,river,air,pathways,incidents,amenities",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=settings.ingestion_poll_interval_sec,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sources = (
        [s.strip() for s in args.sources.split(",") if s.strip()]
        if args.sources
        else None
    )

    if args.once:
        counts = asyncio.run(ingest_once(sources=sources, publish=not args.no_kafka))
        print("Ingest counts:", counts)
        sys.exit(0 if all(v >= 0 for v in counts.values()) else 1)

    asyncio.run(run_loop(args.interval, sources))


if __name__ == "__main__":
    cli()
