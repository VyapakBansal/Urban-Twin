"""Offline training CLI: 5y+ history → LightGBM multi-horizon models."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from urban_twin.config import settings
from urban_twin.forecast.history import (
    fetch_ec_river_levels,
    fetch_open_meteo_pm25,
    fetch_open_meteo_temps,
)
from urban_twin.forecast.lightgbm_model import train_lightgbm_multi

logger = logging.getLogger(__name__)

UNITS = {
    "temp": "C",
    "river_level": "m",
    "aqi_pm25": "ug/m3",
}


async def train_all(*, targets: list[str], days: int, horizons: list[int]) -> int:
    failures = 0
    for target in targets:
        try:
            if target == "temp":
                values, times = await fetch_open_meteo_temps(days=days)
            elif target == "river_level":
                values, times = await fetch_ec_river_levels(days=max(days, 365 * 5))
            elif target in ("aqi_pm25", "air", "pm25"):
                target = "aqi_pm25"
                values, times = await fetch_open_meteo_pm25(days=days)
            else:
                logger.error("unsupported target %s", target)
                failures += 1
                continue

            if len(values) < 1000:
                logger.error("%s: only %s points — need more history", target, len(values))
                failures += 1
                continue

            bundle = train_lightgbm_multi(
                values,
                times,
                reading_type=target,
                horizons=horizons,
                model_version=settings.forecast_model_version,
                unit=UNITS.get(target, ""),
            )
            print(
                f"OK {target} multi-horizon LightGBM  "
                f"horizons={bundle.horizons}  "
                f"-> models/{target}_multih.joblib"
            )
            for h, m in sorted(bundle.metrics.items()):
                print(
                    f"   {h:>3}h  n_train={m.n_train} n_val={m.n_val}  "
                    f"val MAE={m.val_mae:.4f} RMSE={m.val_rmse:.4f}"
                )
        except Exception as exc:
            failures += 1
            logger.exception("training failed for %s: %s", target, exc)
            print(f"FAIL {target}: {exc}", file=sys.stderr)
    return failures


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Train LightGBM multi-horizon models (5y+ history; ~10-30 min)",
    )
    parser.add_argument(
        "--targets",
        default=",".join(settings.forecast_target_list),
        help="Comma list: temp,river_level,aqi_pm25",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=settings.forecast_train_days,
        help="Days of history (default 1826 ≈ 5 years)",
    )
    parser.add_argument(
        "--horizons",
        default=",".join(str(h) for h in settings.forecast_horizon_list),
        help="Comma list of hour horizons, e.g. 1,2,3,6,12,24,48",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    horizons = [int(h.strip()) for h in args.horizons.split(",") if h.strip()]
    code = asyncio.run(train_all(targets=targets, days=args.days, horizons=horizons))
    sys.exit(code)


if __name__ == "__main__":
    cli()
