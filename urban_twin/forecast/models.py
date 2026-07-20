"""Forecasting baselines for 1-hour-ahead prediction.

Start simple and validated: persistence (last value) is the Week 3 baseline.
A moving-average variant is included for comparison when enough history exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np


@dataclass(frozen=True)
class ForecastResult:
    predicted_value: float
    target_time: datetime
    model_version: str
    notes: str


@dataclass(frozen=True)
class ValidationMetrics:
    model_version: str
    n_samples: int
    mae: float
    rmse: float


def persistence_forecast(
    values: list[float],
    recorded_at: list[datetime],
    *,
    horizon: timedelta,
    model_version: str = "persistence-v1",
) -> ForecastResult:
    """Predict value at t+horizon = last observed value (naive baseline)."""
    if not values or not recorded_at:
        raise ValueError("need at least one observation")
    # Assume lists are time-ordered ascending
    last_t = recorded_at[-1]
    if last_t.tzinfo is None:
        last_t = last_t.replace(tzinfo=timezone.utc)
    return ForecastResult(
        predicted_value=float(values[-1]),
        target_time=last_t + horizon,
        model_version=model_version,
        notes="persistence: predicted = last observed value",
    )


def moving_average_forecast(
    values: list[float],
    recorded_at: list[datetime],
    *,
    horizon: timedelta,
    window: int = 5,
    model_version: str = "moving-avg-v1",
) -> ForecastResult:
    if not values:
        raise ValueError("need at least one observation")
    w = min(window, len(values))
    pred = float(np.mean(values[-w:]))
    last_t = recorded_at[-1]
    if last_t.tzinfo is None:
        last_t = last_t.replace(tzinfo=timezone.utc)
    return ForecastResult(
        predicted_value=pred,
        target_time=last_t + horizon,
        model_version=model_version,
        notes=f"moving average over last {w} observations",
    )


def walk_forward_persistence_metrics(
    values: list[float],
    *,
    min_train: int = 3,
) -> ValidationMetrics | None:
    """Time-ordered walk-forward: at each step, predict next = last train value.

    Returns None if not enough points for an honest split.
    """
    if len(values) < min_train + 1:
        return None

    errors: list[float] = []
    for i in range(min_train, len(values)):
        pred = values[i - 1]
        actual = values[i]
        errors.append(actual - pred)

    arr = np.asarray(errors, dtype=float)
    mae = float(np.mean(np.abs(arr)))
    rmse = float(np.sqrt(np.mean(arr**2)))
    return ValidationMetrics(
        model_version="persistence-v1",
        n_samples=len(errors),
        mae=mae,
        rmse=rmse,
    )


def walk_forward_moving_avg_metrics(
    values: list[float],
    *,
    window: int = 5,
    min_train: int = 5,
) -> ValidationMetrics | None:
    if len(values) < min_train + 1:
        return None

    errors: list[float] = []
    for i in range(min_train, len(values)):
        w = min(window, i)
        pred = float(np.mean(values[i - w : i]))
        actual = values[i]
        errors.append(actual - pred)

    arr = np.asarray(errors, dtype=float)
    return ValidationMetrics(
        model_version="moving-avg-v1",
        n_samples=len(errors),
        mae=float(np.mean(np.abs(arr))),
        rmse=float(np.sqrt(np.mean(arr**2))),
    )
