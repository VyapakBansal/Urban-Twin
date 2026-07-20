"""LightGBM multi-horizon forecasting — industry-standard GBDT for tabular time series.

Trains one model per horizon (e.g. 1h, 2h, … 48h) on ≥5 years of hourly history.
Inference supports exact horizons or interpolation to an arbitrary target timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

from urban_twin.config import settings
from urban_twin.forecast.features import build_supervised, latest_feature_row, resample_hourly
from urban_twin.forecast.models import ForecastResult


@dataclass
class HorizonMetrics:
    horizon_hours: int
    train_mae: float
    train_rmse: float
    val_mae: float
    val_rmse: float
    n_train: int
    n_val: int


@dataclass
class MultiHorizonBundle:
    """One LightGBM regressor per forecast horizon."""

    models: dict[int, lgb.LGBMRegressor]
    feature_names: list[str]
    reading_type: str
    horizons: list[int]
    metrics: dict[int, HorizonMetrics]
    model_version: str
    unit: str = ""
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def available_horizons(self) -> list[int]:
        return sorted(self.models.keys())

    def predict_horizon(
        self,
        values: list[float],
        times: list,
        horizon_hours: int,
    ) -> ForecastResult | None:
        y, ts = resample_hourly(values, times)
        row = latest_feature_row(y, ts)
        if row is None:
            return None

        pred, used_h, note = self._predict_row(row, horizon_hours)
        last_t = times[-1]
        if getattr(last_t, "tzinfo", None) is None:
            last_t = last_t.replace(tzinfo=timezone.utc)
        m = self.metrics.get(used_h)
        val_note = (
            f"val MAE={m.val_mae:.4f} RMSE={m.val_rmse:.4f}" if m else "no val metrics"
        )
        return ForecastResult(
            predicted_value=pred,
            target_time=last_t + timedelta(hours=horizon_hours),
            model_version=self.model_version,
            notes=(
                f"LightGBM multi-horizon; requested={horizon_hours}h used={used_h}h; "
                f"{val_note}; {note}"
            ),
        )

    def predict_at(
        self,
        values: list[float],
        times: list,
        target_time: datetime,
    ) -> ForecastResult | None:
        last_t = times[-1]
        if getattr(last_t, "tzinfo", None) is None:
            last_t = last_t.replace(tzinfo=timezone.utc)
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        delta_h = (target_time - last_t).total_seconds() / 3600.0
        if delta_h <= 0:
            raise ValueError("target_time must be after the latest observation")
        # Round to nearest hour for horizon matching; keep exact target_time in result
        horizon = max(1, int(round(delta_h)))
        result = self.predict_horizon(values, times, horizon)
        if result is None:
            return None
        return ForecastResult(
            predicted_value=result.predicted_value,
            target_time=target_time,
            model_version=result.model_version,
            notes=result.notes + f"; at_offset_h={delta_h:.2f}",
        )

    def predict_many(
        self,
        values: list[float],
        times: list,
        horizons: list[int],
    ) -> list[ForecastResult]:
        out: list[ForecastResult] = []
        for h in horizons:
            r = self.predict_horizon(values, times, h)
            if r is not None:
                out.append(r)
        return out

    def _predict_row(
        self,
        row: np.ndarray,
        horizon_hours: int,
    ) -> tuple[float, int, str]:
        hs = self.available_horizons()
        if not hs:
            raise ValueError("bundle has no trained horizons")
        if horizon_hours in self.models:
            pred = float(self.models[horizon_hours].predict(row)[0])
            return pred, horizon_hours, "exact horizon"
        # Linear interpolate between nearest trained horizons
        lo = max((h for h in hs if h <= horizon_hours), default=None)
        hi = min((h for h in hs if h >= horizon_hours), default=None)
        if lo is None:
            pred = float(self.models[hi].predict(row)[0])  # type: ignore[index]
            return pred, hi, "clamped to min trained horizon"  # type: ignore[return-value]
        if hi is None:
            pred = float(self.models[lo].predict(row)[0])
            return pred, lo, "clamped to max trained horizon"
        if lo == hi:
            pred = float(self.models[lo].predict(row)[0])
            return pred, lo, "exact"
        p_lo = float(self.models[lo].predict(row)[0])
        p_hi = float(self.models[hi].predict(row)[0])
        w = (horizon_hours - lo) / (hi - lo)
        pred = p_lo + w * (p_hi - p_lo)
        return pred, horizon_hours, f"interpolated between {lo}h and {hi}h"


def multi_model_path(reading_type: str) -> Path:
    root = Path(settings.forecast_model_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{reading_type}_multih.joblib"


def train_lightgbm_multi(
    values: list[float],
    times: list,
    *,
    reading_type: str,
    horizons: list[int] | None = None,
    model_version: str | None = None,
    unit: str = "",
) -> MultiHorizonBundle:
    horizons = horizons or settings.forecast_horizon_list
    model_version = model_version or settings.forecast_model_version
    horizons = sorted({int(h) for h in horizons if int(h) >= 1})
    if not horizons:
        raise ValueError("need at least one horizon ≥ 1")

    y, ts = resample_hourly(values, times)
    max_h = max(horizons)
    # Shared feature matrix at max horizon length so all targets align on same origins
    X_full, _, names = build_supervised(y, ts, horizon=max_h)
    if len(X_full) < 500:
        raise ValueError(
            f"need ≥500 supervised samples for {reading_type}; got {len(X_full)} "
            f"(raw={len(values)}). Fetch more history."
        )

    models: dict[int, lgb.LGBMRegressor] = {}
    metrics: dict[int, HorizonMetrics] = {}

    for h in horizons:
        X, yt, _ = build_supervised(y, ts, horizon=h)
        # Align to shortest common length with max-horizon feature set if needed
        n = len(yt)
        cut = int(n * 0.8)
        X_train, X_val = X[:cut], X[cut:]
        y_train, y_val = yt[:cut], yt[cut:]

        model = lgb.LGBMRegressor(
            n_estimators=800,
            learning_rate=0.05,
            num_leaves=63,
            max_depth=8,
            min_child_samples=40,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=42,
            n_jobs=-1,
            verbosity=-1,
        )
        model.fit(
            X_train,
            y_train,
            eval_X=X_val,
            eval_y=y_val,
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)
        metrics[h] = HorizonMetrics(
            horizon_hours=h,
            train_mae=float(mean_absolute_error(y_train, train_pred)),
            train_rmse=float(np.sqrt(mean_squared_error(y_train, train_pred))),
            val_mae=float(mean_absolute_error(y_val, val_pred)),
            val_rmse=float(np.sqrt(mean_squared_error(y_val, val_pred))),
            n_train=len(y_train),
            n_val=len(y_val),
        )
        models[h] = model

    bundle = MultiHorizonBundle(
        models=models,
        feature_names=names,
        reading_type=reading_type,
        horizons=horizons,
        metrics=metrics,
        model_version=model_version,
        unit=unit,
    )
    joblib.dump(bundle, multi_model_path(reading_type))
    return bundle


def load_multi_bundle(reading_type: str) -> MultiHorizonBundle | None:
    path = multi_model_path(reading_type)
    if not path.exists():
        return None
    return joblib.load(path)
