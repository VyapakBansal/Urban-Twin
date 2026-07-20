# Tests for LightGBM multi-horizon predict helpers (no network).

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

lightgbm = pytest.importorskip("lightgbm")

from urban_twin.forecast.features import build_supervised, resample_hourly
from urban_twin.forecast.lightgbm_model import MultiHorizonBundle, train_lightgbm_multi


def _synth_series(n: int = 800):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    times = [start + timedelta(hours=i) for i in range(n)]
    values = [10.0 + 5.0 * np.sin(2 * np.pi * i / 24) + 0.01 * i for i in range(n)]
    return values, times


def test_train_and_predict_horizon():
    values, times = _synth_series()
    bundle = train_lightgbm_multi(
        values,
        times,
        reading_type="temp",
        horizons=[1, 2, 6],
        model_version="test-lgbm",
        unit="C",
    )
    assert 1 in bundle.models
    result = bundle.predict_horizon(values, times, 2)
    assert result is not None
    assert result.model_version == "test-lgbm"
    assert abs((result.target_time - times[-1]).total_seconds() - 7200) < 1


def test_predict_at_and_interpolate():
    values, times = _synth_series()
    bundle = train_lightgbm_multi(
        values,
        times,
        reading_type="temp",
        horizons=[1, 6],
        model_version="test-lgbm",
    )
    # horizon 3 is between 1 and 6 → interpolation path
    mid = bundle.predict_horizon(values, times, 3)
    assert mid is not None
    assert "interpolat" in (mid.notes or "").lower() or "exact" in (mid.notes or "").lower()

    at = times[-1] + timedelta(hours=2)
    at_res = bundle.predict_at(values, times, at)
    assert at_res is not None
    assert at_res.target_time == at


def test_resample_supervised_smoke():
    values, times = _synth_series(200)
    y, ts = resample_hourly(values, times)
    X, yt, names = build_supervised(y, ts, horizon=2)
    assert len(X) == len(yt)
    assert len(names) > 5
