"""Forecast worker: load trained 24h models (or baselines) → PostGIS + Kafka."""

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
from urban_twin.forecast.gbr import load_bundle
from urban_twin.forecast.history import (
    fetch_ec_river_levels,
    fetch_open_meteo_pm25,
    fetch_open_meteo_temps,
)
from urban_twin.forecast.lightgbm_model import load_multi_bundle
from urban_twin.forecast.models import (
    moving_average_forecast,
    persistence_forecast,
    walk_forward_moving_avg_metrics,
    walk_forward_persistence_metrics,
)

logger = logging.getLogger(__name__)


def _station_for(reading_type: str) -> str:
    if reading_type == "river_level":
        return f"bow-{settings.river_station_id}"
    return settings.station_id


def _coords_for(reading_type: str) -> tuple[float, float]:
    # Bow gauge is slightly SE of Kensington AOI centroid — close enough for map
    if reading_type == "river_level":
        return settings.station_lon + 0.008, settings.station_lat - 0.004
    return settings.station_lon, settings.station_lat


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


async def _series_for_gbr(
    reading_type: str,
    live_values: list[float],
    live_times: list,
) -> tuple[list[float], list]:
    """Merge recent archive context with live points so lag features are available."""
    if reading_type == "temp":
        hist_v, hist_t = await fetch_open_meteo_temps(days=60)
    elif reading_type == "river_level":
        hist_v, hist_t = await fetch_ec_river_levels(days=120)
    elif reading_type == "aqi_pm25":
        hist_v, hist_t = await fetch_open_meteo_pm25(days=60)
    else:
        return live_values, live_times

    by_hour: dict = {}
    for v, t in zip(hist_v, hist_t, strict=True):
        key = t.replace(minute=0, second=0, microsecond=0)
        by_hour[key] = float(v)
    for v, t in zip(live_values, live_times, strict=True):
        if t.tzinfo is None:
            from datetime import timezone

            t = t.replace(tzinfo=timezone.utc)
        key = t.replace(minute=0, second=0, microsecond=0)
        by_hour[key] = float(v)
    ordered = sorted(by_hour.items(), key=lambda x: x[0])
    return [v for _, v in ordered], [t for t, _ in ordered]


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
    model: str = "lgbm",
) -> Forecast | None:
    reading_type = reading_type or settings.forecast_reading_type
    station_id = station_id or _station_for(reading_type)
    horizon = timedelta(hours=settings.forecast_horizon_hours)
    lon, lat = _coords_for(reading_type)

    live_values, live_times = await _load_series(station_id, reading_type)
    if not live_values and model not in ("lgbm", "gbr"):
        logger.warning("no readings for %s/%s — skip forecast", station_id, reading_type)
        return None

    result = None
    if model == "lgbm":
        multi = load_multi_bundle(reading_type)
        if multi is None:
            logger.warning(
                "no LightGBM multi model for %s — run: python -m urban_twin.forecast.train",
                reading_type,
            )
            return None
        values, times = await _series_for_gbr(reading_type, live_values, live_times)
        result = multi.predict_horizon(values, times, settings.forecast_horizon_hours)
        if result is None:
            fallback_v = live_values or values
            fallback_t = live_times or times
            if not fallback_v:
                return None
            result = persistence_forecast(
                fallback_v,
                fallback_t,
                horizon=horizon,
                model_version=f"{multi.model_version}+persistence-fallback",
            )
    elif model == "gbr":
        bundle = load_bundle(reading_type, settings.forecast_horizon_hours)
        if bundle is None:
            logger.warning(
                "no HistGBR model for %s — run older train or use --model lgbm",
                reading_type,
            )
            return None
        values, times = await _series_for_gbr(reading_type, live_values, live_times)
        result = bundle.predict_next(values, times)
        if result is None:
            fallback_v = live_values or values
            fallback_t = live_times or times
            if not fallback_v:
                return None
            result = persistence_forecast(
                fallback_v,
                fallback_t,
                horizon=horizon,
                model_version=f"{bundle.model_version}+persistence-fallback",
            )
    elif model == "moving_avg":
        result = moving_average_forecast(live_values, live_times, horizon=horizon)
    else:
        result = persistence_forecast(
            live_values,
            live_times,
            horizon=horizon,
            model_version=settings.forecast_model_version,
        )

    async with AsyncSessionLocal() as session:
        row = Forecast(
            station_id=station_id,
            geometry=WKTElement(f"POINT({lon} {lat})", srid=4326),
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
                "lon": lon,
                "lat": lat,
            }
        )

    return row


async def generate_all(
    *,
    publish: bool = True,
    model: str = "gbr",
) -> list[Forecast]:
    rows: list[Forecast] = []
    for target in settings.forecast_target_list:
        row = await generate_once(
            reading_type=target,
            publish=publish,
            model=model,
        )
        if row is not None:
            rows.append(row)
    return rows


async def validate_models(
    *,
    station_id: str | None = None,
    reading_type: str | None = None,
) -> None:
    targets = (
        [reading_type]
        if reading_type
        else settings.forecast_target_list
    )
    for rt in targets:
        sid = station_id or _station_for(rt)
        values, _ = await _load_series(sid, rt)
        print(f"\nstation={sid} reading_type={rt} n_obs={len(values)}")

        bundle = load_bundle(rt, settings.forecast_horizon_hours)
        if bundle:
            print(
                f"  {bundle.model_version}  "
                f"val n={bundle.n_val}  MAE={bundle.val_mae:.4f}  "
                f"RMSE={bundle.val_rmse:.4f}  "
                f"(trained offline; n_train={bundle.n_train})"
            )
        else:
            print("  gbr model not found — run urban_twin.forecast.train")

        p = walk_forward_persistence_metrics(values)
        m = walk_forward_moving_avg_metrics(values)
        if p:
            print(f"  persistence-v1  n={p.n_samples}  MAE={p.mae:.4f}  RMSE={p.rmse:.4f}")
        else:
            print(
                f"  persistence-v1  not enough live points "
                f"(have {len(values)}; need >=4)"
            )
        if m:
            print(f"  moving-avg-v1   n={m.n_samples}  MAE={m.mae:.4f}  RMSE={m.rmse:.4f}")


async def run_loop(interval_sec: int, model: str) -> None:
    logger.info(
        "forecast loop every %ss model=%s targets=%s horizon=%sh",
        interval_sec,
        model,
        settings.forecast_target_list,
        settings.forecast_horizon_hours,
    )
    while True:
        try:
            await generate_all(model=model)
        except Exception:
            logger.exception("forecast cycle failed")
        await asyncio.sleep(interval_sec)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin forecast worker")
    parser.add_argument("--once", action="store_true", help="Generate forecasts and exit")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Show trained-model val metrics + live walk-forward baselines",
    )
    parser.add_argument(
        "--model",
        choices=("lgbm", "gbr", "persistence", "moving_avg"),
        default="lgbm",
        help="Model to run (default: LightGBM multi-horizon)",
    )
    parser.add_argument(
        "--reading-type",
        default=None,
        help="Single target (default: all FORECAST_TARGETS)",
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
        asyncio.run(validate_models(reading_type=args.reading_type))
        sys.exit(0)

    if args.once:
        if args.reading_type:
            rows = [
                asyncio.run(
                    generate_once(
                        reading_type=args.reading_type,
                        publish=not args.no_kafka,
                        model=args.model,
                    )
                )
            ]
            rows = [r for r in rows if r is not None]
        else:
            rows = asyncio.run(
                generate_all(publish=not args.no_kafka, model=args.model)
            )
        if not rows:
            print(
                "No forecasts generated. Train models first:\n"
                "  .venv/Scripts/python.exe -m urban_twin.forecast.train\n"
                "And ensure live readings exist for temp / river_level."
            )
            sys.exit(1)
        for row in rows:
            print(
                f"Forecast id={row.id} {row.reading_type}={row.predicted_value:.4f} "
                f"target={row.target_time.isoformat()} model={row.model_version}"
            )
        sys.exit(0)

    asyncio.run(run_loop(args.interval, args.model))


if __name__ == "__main__":
    cli()
