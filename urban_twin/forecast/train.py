"""Offline training CLI: download history → train 24h GBR models → save to models/."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from urban_twin.config import settings
from urban_twin.forecast.gbr import train_gbr
from urban_twin.forecast.history import fetch_ec_river_levels, fetch_open_meteo_temps

logger = logging.getLogger(__name__)


async def train_all(*, targets: list[str], days: int) -> int:
    failures = 0
    for target in targets:
        try:
            if target == "temp":
                values, times = await fetch_open_meteo_temps(days=days)
            elif target == "river_level":
                values, times = await fetch_ec_river_levels(days=max(days, 365 * 5))
            else:
                logger.error("unsupported target %s", target)
                failures += 1
                continue

            if len(values) < 500:
                logger.error(
                    "%s: only %s points — need more history before training",
                    target,
                    len(values),
                )
                failures += 1
                continue

            bundle = train_gbr(
                values,
                times,
                reading_type=target,
                horizon=settings.forecast_horizon_hours,
                model_version=settings.forecast_model_version,
            )
            print(
                f"OK {target} {bundle.horizon_hours}h  "
                f"n_train={bundle.n_train} n_val={bundle.n_val}  "
                f"train MAE={bundle.train_mae:.4f} RMSE={bundle.train_rmse:.4f}  "
                f"val MAE={bundle.val_mae:.4f} RMSE={bundle.val_rmse:.4f}  "
                f"-> models/{target}_{bundle.horizon_hours}h.joblib"
            )
        except Exception as exc:
            failures += 1
            logger.exception("training failed for %s: %s", target, exc)
            print(f"FAIL {target}: {exc}", file=sys.stderr)
    return failures


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Train 24h-ahead Gradient Boosting models (temp + river level)",
    )
    parser.add_argument(
        "--targets",
        default=",".join(settings.forecast_target_list),
        help="Comma-separated: temp,river_level",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=settings.forecast_train_days,
        help="Days of Open-Meteo history for temp (river uses ≥5y daily)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    code = asyncio.run(train_all(targets=targets, days=args.days))
    sys.exit(code)


if __name__ == "__main__":
    cli()
