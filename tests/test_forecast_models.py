"""Tests for forecast feature engineering and baselines."""

from datetime import datetime, timedelta, timezone

import numpy as np

from urban_twin.forecast.features import build_supervised, resample_hourly
from urban_twin.forecast.models import (
    moving_average_forecast,
    persistence_forecast,
    walk_forward_persistence_metrics,
)


def test_persistence_forecast():
    times = [datetime(2024, 1, 1, tzinfo=timezone.utc)]
    values = [10.0]
    result = persistence_forecast(values, times, horizon=timedelta(hours=24))
    assert result.predicted_value == 10.0
    assert result.target_time == times[0] + timedelta(hours=24)


def test_moving_average_forecast():
    times = [
        datetime(2024, 1, 1, i, tzinfo=timezone.utc) for i in range(5)
    ]
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = moving_average_forecast(
        values, times, horizon=timedelta(hours=24), window=3
    )
    assert result.predicted_value == 4.0


def test_walk_forward_persistence():
    metrics = walk_forward_persistence_metrics([1.0, 2.0, 3.0, 4.0, 5.0])
    assert metrics is not None
    assert metrics.n_samples == 2


def test_resample_and_supervised_24h():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    times = [start + timedelta(hours=i) for i in range(120)]
    values = [float(10 + (i % 24) * 0.5) for i in range(120)]
    y, ts = resample_hourly(values, times)
    assert len(y) == 120
    X, yt, names = build_supervised(y, ts, horizon=24)
    assert len(names) >= 10
    assert len(X) == len(yt)
    assert len(X) > 40
    assert np.isfinite(X).all()
