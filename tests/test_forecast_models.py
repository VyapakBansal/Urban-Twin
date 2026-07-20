"""Tests for forecast baselines (no DB / network)."""

from datetime import datetime, timedelta, timezone

from urban_twin.forecast.models import (
    moving_average_forecast,
    persistence_forecast,
    walk_forward_persistence_metrics,
)


def test_persistence_forecast():
    t0 = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    times = [t0, t0 + timedelta(minutes=5)]
    values = [18.0, 20.5]
    result = persistence_forecast(values, times, horizon=timedelta(hours=1))
    assert result.predicted_value == 20.5
    assert result.target_time == times[-1] + timedelta(hours=1)
    assert result.model_version == "persistence-v1"


def test_moving_average_forecast():
    t0 = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    times = [t0 + timedelta(minutes=i) for i in range(5)]
    values = [10.0, 12.0, 14.0, 16.0, 18.0]
    result = moving_average_forecast(values, times, horizon=timedelta(hours=1), window=3)
    assert result.predicted_value == 16.0  # mean of 14,16,18


def test_walk_forward_persistence_metrics():
    values = [10.0, 11.0, 13.0, 12.0, 14.0]
    metrics = walk_forward_persistence_metrics(values, min_train=3)
    assert metrics is not None
    assert metrics.n_samples == 2
    assert metrics.mae >= 0
    assert metrics.rmse >= metrics.mae or abs(metrics.rmse - metrics.mae) < 1e-9
