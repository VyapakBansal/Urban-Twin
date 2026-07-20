"""Forecast worker: read history → baseline model → PostGIS + Kafka."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import timedelta

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from urban_twin.config import settings
from urban_twin.db.models import Forecast, SensorReading
from urban_twin.db.session import AsyncSessionLocal
from urban_twin.forecast.models import (
    moving_average_forecast,
    persistence_forecast,
    walk_forward_moving_avg_metrics,
    walk_forward_persistence_metrics,
)

logger = logging.getLogger(__name__)


async def _load_series(
    station_id: str,
    reading_type: str,
) -> tuple[list[float], list]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(SensorReading.value, SensorReading.recorded_at)
            .where(SensorReading.station_id == station_id)
            .where(SensorReading.reading_type == reading_type)
            .order_by(SensorReading.recorded_at.asc())
        )
        rows = (await session.execute(stmt)).all()
    values = [float(r.value) for r in rows]
    times = [r.recorded_at for r in rows]
    return values, times


async def _publish_forecast_event(payload: dict) -> None:
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    )
    await producer.start()
    try:
        await producer.send_and_wait(
            settings.kafka_topic_forecasts,
            value=payload,
            key=payload["station_id"].encode("utf-8"),
        )
    finally:
        await producer.stop()


async def generate_once(
    *,
    station_id: str | None = None,
    reading_type: str | None = None,
    publish: bool = True,
    model: str = "persistence",
) -> Forecast | None:
    station_id = station_id or settings.station_id
    reading_type = reading_type or settings.forecast_reading_type
    horizon = timedelta(hours=settings.forecast_horizon_hours)

    values, times = await _load_series(station_id, reading_type)
    if not values:
        logger.warning("no readings for %s/%s — skip forecast", station_id, reading_type)
        return None

    if model == "moving_avg":
        result = moving_average_forecast(values, times, horizon=horizon)
    else:
        result = persistence_forecast(
            values,
            times,
            horizon=horizon,
            model_version=settings.forecast_model_version,
        )

    async with AsyncSessionLocal() as session:
        row = Forecast(
            station_id=station_id,
            geometry=WKTElement(
                f"POINT({settings.station_lon} {settings.station_lat})",
                srid=4326,
            ),
            reading_type=reading_type,
            predicted_value=result.predicted_value,
            target_time=result.target_time,
            model_version=result.model_version,
            notes=result.notes,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    logger.info(
        "forecast %s=%s @ %s (%s)",
        reading_type,
        result.predicted_value,
        result.target_time.isoformat(),
        result.model_version,
    )

    if publish:
        await _publish_forecast_event(
            {
                "station_id": station_id,
                "reading_type": reading_type,
                "predicted_value": result.predicted_value,
                "target_time": result.target_time,
                "model_version": result.model_version,
                "forecast_id": row.id,
                "lon": settings.station_lon,
                "lat": settings.station_lat,
            }
        )

    return row


async def validate_models(
    *,
    station_id: str | None = None,
    reading_type: str | None = None,
) -> None:
    station_id = station_id or settings.station_id
    reading_type = reading_type or settings.forecast_reading_type
    values, _ = await _load_series(station_id, reading_type)

    p = walk_forward_persistence_metrics(values)
    m = walk_forward_moving_avg_metrics(values)

    if p is None:
        print(
            f"Not enough {reading_type} points for walk-forward validation "
            f"(have {len(values)}; need ≥4). Keep ingesting and retry."
        )
        return

    print(f"station={station_id} reading_type={reading_type} n_obs={len(values)}")
    print(f"  persistence-v1  n={p.n_samples}  MAE={p.mae:.4f}  RMSE={p.rmse:.4f}")
    if m:
        print(f"  moving-avg-v1   n={m.n_samples}  MAE={m.mae:.4f}  RMSE={m.rmse:.4f}")
    else:
        print("  moving-avg-v1   insufficient history (need ≥6 points)")


async def run_loop(interval_sec: int, model: str) -> None:
    logger.info("forecast loop every %ss model=%s", interval_sec, model)
    while True:
        try:
            await generate_once(model=model)
        except Exception:
            logger.exception("forecast cycle failed")
        await asyncio.sleep(interval_sec)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin forecast worker")
    parser.add_argument("--once", action="store_true", help="Generate one forecast and exit")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Walk-forward MAE/RMSE on stored readings (time-ordered)",
    )
    parser.add_argument(
        "--model",
        choices=("persistence", "moving_avg"),
        default="persistence",
        help="Baseline model to run",
    )
    parser.add_argument("--no-kafka", action="store_true")
    parser.add_argument(
        "--interval",
        type=int,
        default=settings.forecast_interval_sec,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.validate:
        asyncio.run(validate_models())
        sys.exit(0)

    if args.once:
        row = asyncio.run(
            generate_once(publish=not args.no_kafka, model=args.model)
        )
        if row is None:
            print("No forecast generated (no readings?)")
            sys.exit(1)
        print(
            f"Forecast id={row.id} {row.reading_type}={row.predicted_value} "
            f"target={row.target_time.isoformat()} model={row.model_version}"
        )
        sys.exit(0)

    asyncio.run(run_loop(args.interval, args.model))


if __name__ == "__main__":
    cli()
