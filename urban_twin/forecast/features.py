"""Hourly feature engineering for multi-hour-ahead forecasting."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

# Lags in hours (relative to prediction origin t)
LAG_HOURS = (1, 2, 3, 6, 12, 24, 48)
ROLL_WINDOWS = (3, 6, 24)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resample_hourly(
    values: list[float],
    times: list[datetime],
) -> tuple[np.ndarray, np.ndarray]:
    """Mean-aggregate irregular observations onto an hourly UTC grid."""
    if not values:
        return np.array([], dtype=float), np.array([], dtype="datetime64[h]")

    buckets: dict[datetime, list[float]] = {}
    for v, t in zip(values, times, strict=True):
        t = _to_utc(t).replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(t, []).append(float(v))

    keys = sorted(buckets)
    y = np.asarray([float(np.mean(buckets[k])) for k in keys], dtype=float)
    # Store as naive UTC hour stamps for numpy convenience
    ts = np.asarray([np.datetime64(k.replace(tzinfo=None), "h") for k in keys])
    return y, ts


def build_supervised(
    y: np.ndarray,
    times: np.ndarray,
    *,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build X, y for predicting y[t+horizon] from history at t."""
    max_lag = max(LAG_HOURS)
    feature_names: list[str] = (
        [f"lag_{h}h" for h in LAG_HOURS]
        + [f"roll_mean_{w}h" for w in ROLL_WINDOWS]
        + [f"roll_std_{w}h" for w in ROLL_WINDOWS]
        + ["hour_sin", "hour_cos", "doy_sin", "doy_cos"]
    )

    rows: list[list[float]] = []
    targets: list[float] = []
    n = len(y)
    for t in range(max_lag, n - horizon):
        feats: list[float] = []
        for h in LAG_HOURS:
            feats.append(float(y[t - h]))
        for w in ROLL_WINDOWS:
            window = y[t - w + 1 : t + 1]
            feats.append(float(np.mean(window)))
            feats.append(float(np.std(window) if len(window) > 1 else 0.0))

        # Calendar features from origin time
        origin = times[t].astype("datetime64[s]").astype(datetime)
        hour = origin.hour
        doy = origin.timetuple().tm_yday
        feats.append(float(np.sin(2 * np.pi * hour / 24)))
        feats.append(float(np.cos(2 * np.pi * hour / 24)))
        feats.append(float(np.sin(2 * np.pi * doy / 365.25)))
        feats.append(float(np.cos(2 * np.pi * doy / 365.25)))

        rows.append(feats)
        targets.append(float(y[t + horizon]))

    if not rows:
        return (
            np.empty((0, len(feature_names))),
            np.empty((0,)),
            feature_names,
        )
    return np.asarray(rows, dtype=float), np.asarray(targets, dtype=float), feature_names


def latest_feature_row(
    y: np.ndarray,
    times: np.ndarray,
) -> np.ndarray | None:
    """Features at the last usable origin (needs max lag history)."""
    max_lag = max(LAG_HOURS)
    if len(y) <= max_lag:
        return None
    t = len(y) - 1
    feats: list[float] = []
    for h in LAG_HOURS:
        feats.append(float(y[t - h]))
    for w in ROLL_WINDOWS:
        window = y[t - w + 1 : t + 1]
        feats.append(float(np.mean(window)))
        feats.append(float(np.std(window) if len(window) > 1 else 0.0))
    origin = times[t].astype("datetime64[s]").astype(datetime)
    hour = origin.hour
    doy = origin.timetuple().tm_yday
    feats.append(float(np.sin(2 * np.pi * hour / 24)))
    feats.append(float(np.cos(2 * np.pi * hour / 24)))
    feats.append(float(np.sin(2 * np.pi * doy / 365.25)))
    feats.append(float(np.cos(2 * np.pi * doy / 365.25)))
    return np.asarray(feats, dtype=float).reshape(1, -1)
