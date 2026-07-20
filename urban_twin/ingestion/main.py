"""Ingestion service: poll OpenWeather → validate → PostGIS → Kafka.

Week 2: after each DB write, publish ReadingEvent messages to sensor.readings.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from urban_twin.config import settings
from urban_twin.db.session import AsyncSessionLocal
from urban_twin.ingestion.client import OpenWeatherClient
from urban_twin.ingestion.normalize import normalize_openweather_current
from urban_twin.ingestion.persist import write_readings
from urban_twin.messaging.producer import publish_readings
from urban_twin.messaging.schemas import ReadingEvent

logger = logging.getLogger(__name__)


async def ingest_once(*, publish: bool = True) -> int:
    client = OpenWeatherClient(settings.openweather_api_key)
    payload = await client.fetch_current(settings.station_lat, settings.station_lon)
    readings = normalize_openweather_current(
        payload,
        station_id=settings.station_id,
        lon=settings.station_lon,
        lat=settings.station_lat,
    )

    async with AsyncSessionLocal() as session:
        rows = await write_readings(session, readings)

    for row in rows:
        logger.info(
            "wrote %s=%s %s @ %s (id=%s)",
            row.reading_type,
            row.value,
            row.unit,
            row.recorded_at.isoformat(),
            row.id,
        )

    if publish:
        events = [
            ReadingEvent(
                station_id=row.station_id,
                lon=settings.station_lon,
                lat=settings.station_lat,
                reading_type=row.reading_type,
                value=row.value,
                unit=row.unit,
                recorded_at=row.recorded_at,
                reading_id=row.id,
            )
            for row in rows
        ]
        await publish_readings(events)

    return len(rows)


async def run_loop(interval_sec: int) -> None:
    logger.info(
        "starting ingestion loop every %ss for station %s (%.4f, %.4f)",
        interval_sec,
        settings.station_id,
        settings.station_lat,
        settings.station_lon,
    )
    while True:
        try:
            n = await ingest_once()
            logger.info("ingest cycle wrote %s readings", n)
        except Exception:
            logger.exception("ingest cycle failed")
        await asyncio.sleep(interval_sec)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin weather ingestion")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch and write a single batch, then exit",
    )
    parser.add_argument(
        "--no-kafka",
        action="store_true",
        help="Skip publishing to Kafka (DB write only)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=settings.ingestion_poll_interval_sec,
        help="Poll interval seconds when looping (default from .env)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.once:
        count = asyncio.run(ingest_once(publish=not args.no_kafka))
        print(f"Wrote {count} readings")
        sys.exit(0)

    asyncio.run(run_loop(args.interval))


if __name__ == "__main__":
    cli()
