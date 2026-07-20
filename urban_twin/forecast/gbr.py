"""Gradient Boosting Regressor for H-hour-ahead sensor forecasts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from urban_twin.config import settings
from urban_twin.forecast.features import build_supervised, latest_feature_row, resample_hourly
from urban_twin.forecast.models import ForecastResult, ValidationMetrics


@dataclass
class TrainedBundle:
    model: HistGradientBoostingRegressor
    feature_names: list[str]
    reading_type: str
    horizon_hours: int
    train_mae: float
    train_rmse: float
    val_mae: float
    val_rmse: float
    n_train: int
    n_val: int
    model_version: str

    def predict_next(
        self,
        values: list[float],
        times: list,
    ) -> ForecastResult | None:
        from datetime import timedelta, timezone

        y, ts = resample_hourly(values, times)
        row = latest_feature_row(y, ts)
        if row is None:
            return None
        pred = float(self.model.predict(row)[0])
        last_t = times[-1]
        if last_t.tzinfo is None:
            last_t = last_t.replace(tzinfo=timezone.utc)
        return ForecastResult(
            predicted_value=pred,
            target_time=last_t + timedelta(hours=self.horizon_hours),
            model_version=self.model_version,
            notes=(
                f"HistGBR {self.horizon_hours}h-ahead; "
                f"val MAE={self.val_mae:.4f} RMSE={self.val_rmse:.4f} "
                f"(n_train={self.n_train}, n_val={self.n_val})"
            ),
        )


def model_path(reading_type: str, horizon: int | None = None) -> Path:
    horizon = horizon if horizon is not None else settings.forecast_horizon_hours
    root = Path(settings.forecast_model_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{reading_type}_{horizon}h.joblib"


def train_gbr(
    values: list[float],
    times: list,
    *,
    reading_type: str,
    horizon: int | None = None,
    model_version: str | None = None,
) -> TrainedBundle:
    horizon = horizon if horizon is not None else settings.forecast_horizon_hours
    model_version = model_version or settings.forecast_model_version

    y, ts = resample_hourly(values, times)
    X, yt, names = build_supervised(y, ts, horizon=horizon)
    if len(yt) < 200:
        raise ValueError(
            f"need ≥200 supervised samples for {reading_type}; got {len(yt)} "
            f"(raw points={len(values)}). Fetch more history or lower horizon."
        )

    # Time-ordered 80/20 split (no shuffle)
    cut = int(len(yt) * 0.8)
    X_train, X_val = X[:cut], X[cut:]
    y_train, y_val = yt[:cut], yt[cut:]

    model = HistGradientBoostingRegressor(
        max_depth=6,
        max_iter=300,
        learning_rate=0.05,
        min_samples_leaf=20,
        l2_regularization=0.1,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        random_state=42,
    )
    model.fit(X_train, y_train)

    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val)
    train_mae = float(mean_absolute_error(y_train, train_pred))
    train_rmse = float(np.sqrt(mean_squared_error(y_train, train_pred)))
    val_mae = float(mean_absolute_error(y_val, val_pred))
    val_rmse = float(np.sqrt(mean_squared_error(y_val, val_pred)))

    bundle = TrainedBundle(
        model=model,
        feature_names=names,
        reading_type=reading_type,
        horizon_hours=horizon,
        train_mae=train_mae,
        train_rmse=train_rmse,
        val_mae=val_mae,
        val_rmse=val_rmse,
        n_train=len(y_train),
        n_val=len(y_val),
        model_version=model_version,
    )
    joblib.dump(bundle, model_path(reading_type, horizon))
    return bundle


def load_bundle(reading_type: str, horizon: int | None = None) -> TrainedBundle | None:
    path = model_path(reading_type, horizon)
    if not path.exists():
        return None
    return joblib.load(path)


def walk_forward_gbr_metrics(bundle: TrainedBundle) -> ValidationMetrics:
    return ValidationMetrics(
        model_version=bundle.model_version,
        n_samples=bundle.n_val,
        mae=bundle.val_mae,
        rmse=bundle.val_rmse,
    )
