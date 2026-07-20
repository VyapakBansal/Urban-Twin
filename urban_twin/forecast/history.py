"""Fetch large historical series for offline training (Open-Meteo + MSC river)."""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from urban_twin.config import settings

logger = logging.getLogger(__name__)


async def fetch_open_meteo_temps(
    *,
    days: int | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[list[float], list[datetime]]:
    """Hourly 2m temperature from Open-Meteo archive (chunked by year for long spans)."""
    days = days or settings.forecast_train_days
    lat = lat if lat is not None else settings.station_lat
    lon = lon if lon is not None else settings.station_lon
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days)
    return await _fetch_open_meteo_hourly(
        lat=lat,
        lon=lon,
        start=start,
        end=end,
        hourly_var="temperature_2m",
        label="temp",
    )


async def fetch_open_meteo_pm25(
    *,
    days: int | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[list[float], list[datetime]]:
    """Hourly PM2.5 from Open-Meteo air-quality API (no key)."""
    days = days or settings.forecast_train_days
    lat = lat if lat is not None else settings.station_lat
    lon = lon if lon is not None else settings.station_lon
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days)

    values: list[float] = []
    times: list[datetime] = []
    # Air-quality API accepts long ranges; still chunk yearly to be safe
    cursor = start
    async with httpx.AsyncClient(timeout=180.0) as client:
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=365), end)
            url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": cursor.isoformat(),
                "end_date": chunk_end.isoformat(),
                "hourly": "pm2_5",
                "timezone": "UTC",
            }
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            hours = data.get("hourly", {}).get("time", [])
            series = data.get("hourly", {}).get("pm2_5", [])
            for t_str, v in zip(hours, series, strict=False):
                if v is None:
                    continue
                dt = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
                values.append(float(v))
                times.append(dt)
            cursor = chunk_end + timedelta(days=1)

    logger.info("open-meteo pm2.5 history: %s hourly points (%s → %s)", len(values), start, end)
    return values, times


async def _fetch_open_meteo_hourly(
    *,
    lat: float,
    lon: float,
    start: date,
    end: date,
    hourly_var: str,
    label: str,
) -> tuple[list[float], list[datetime]]:
    values: list[float] = []
    times: list[datetime] = []
    cursor = start
    async with httpx.AsyncClient(timeout=180.0) as client:
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=365), end)
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": cursor.isoformat(),
                "end_date": chunk_end.isoformat(),
                "hourly": hourly_var,
                "timezone": "UTC",
            }
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            hours = data.get("hourly", {}).get("time", [])
            series = data.get("hourly", {}).get(hourly_var, [])
            for t_str, v in zip(hours, series, strict=False):
                if v is None:
                    continue
                dt = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
                values.append(float(v))
                times.append(dt)
            cursor = chunk_end + timedelta(days=1)
    logger.info(
        "open-meteo %s history: %s hourly points (%s → %s)",
        label,
        len(values),
        start,
        end,
    )
    return values, times


async def fetch_ec_river_levels(
    *,
    station_id: str | None = None,
    days: int | None = None,
) -> tuple[list[float], list[datetime]]:
    """Long river-level history: MSC daily means (upsampled) + recent hourly CSV."""
    station_id = station_id or settings.river_station_id
    days = days or max(settings.forecast_train_days, 365 * 5)

    daily_v, daily_t = await _fetch_msc_daily_levels(station_id, days=days)
    hourly_v, hourly_t = await _fetch_ec_csv_levels(station_id)

    # Upsample daily → hourly (hold last value) so 24h-ahead training is valid
    up_v, up_t = _upsample_daily_to_hourly(daily_v, daily_t)

    by_t: dict[datetime, float] = {}
    for v, t in zip(up_v, up_t, strict=True):
        by_t[t.replace(minute=0, second=0, microsecond=0)] = v
    # Hourly CSV overwrites overlapping hours (more precise)
    for v, t in zip(hourly_v, hourly_t, strict=True):
        key = t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        by_t[key] = v

    ordered = sorted(by_t.items(), key=lambda x: x[0])
    out_t = [t for t, _ in ordered]
    out_v = [v for _, v in ordered]
    logger.info(
        "river level history merged: %s hourly points "
        "(daily_raw=%s, csv_hourly=%s)",
        len(out_v),
        len(daily_v),
        len(hourly_v),
    )
    return out_v, out_t


async def _fetch_msc_daily_levels(
    station_id: str,
    *,
    days: int,
) -> tuple[list[float], list[datetime]]:
    end = date.today()
    start = end - timedelta(days=days)
    url = "https://api.weather.gc.ca/collections/hydrometric-daily-mean/items"
    params = {
        "STATION_NUMBER": station_id,
        "datetime": f"{start.isoformat()}/{end.isoformat()}",
        "limit": 10000,
        "f": "json",
    }
    values: list[float] = []
    times: list[datetime] = []
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        payload = r.json()

    for feat in payload.get("features", []):
        props = feat.get("properties") or {}
        level = props.get("LEVEL")
        date_str = props.get("DATE")
        if level is None or not date_str:
            continue
        try:
            d = date.fromisoformat(str(date_str)[:10])
        except ValueError:
            continue
        # Anchor daily mean at 12:00 UTC
        dt = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
        values.append(float(level))
        times.append(dt)

    logger.info("MSC daily LEVEL for %s: %s days", station_id, len(values))
    return values, times


async def _fetch_ec_csv_levels(
    station_id: str,
) -> tuple[list[float], list[datetime]]:
    province = "AB"
    urls = [
        f"https://dd.weather.gc.ca/hydrometric/csv/{province}/hourly/"
        f"{province}_{station_id}_hourly_hydrometric.csv",
        f"https://dd.weather.gc.ca/today/hydrometric/csv/{province}/hourly/"
        f"{province}_{station_id}_hourly_hydrometric.csv",
    ]
    values: list[float] = []
    times: list[datetime] = []
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for url in urls:
            try:
                r = await client.get(url)
                if r.status_code != 200:
                    logger.warning("river CSV HTTP %s for %s", r.status_code, url)
                    continue
                v, t = _parse_hydrometric_csv(r.text)
                values.extend(v)
                times.extend(t)
                logger.info("river CSV %s → %s points", url.split("/")[-1], len(v))
            except Exception:
                logger.exception("failed fetching %s", url)
    return values, times


def _upsample_daily_to_hourly(
    values: list[float],
    times: list[datetime],
) -> tuple[list[float], list[datetime]]:
    if not values:
        return [], []
    pairs = sorted(zip(times, values, strict=True), key=lambda x: x[0])
    out_v: list[float] = []
    out_t: list[datetime] = []
    for i, (t, v) in enumerate(pairs):
        start = t.replace(hour=0, minute=0, second=0, microsecond=0)
        if i + 1 < len(pairs):
            end = pairs[i + 1][0].replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            end = start + timedelta(days=1)
        cursor = start
        while cursor < end:
            out_t.append(cursor.replace(tzinfo=timezone.utc))
            out_v.append(float(v))
            cursor += timedelta(hours=1)
    return out_v, out_t


def _parse_hydrometric_csv(text: str) -> tuple[list[float], list[datetime]]:
    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], []

    time_keys = ("Date", "Date/Time", "Datetime", "date")
    level_keys = (
        "Water Level / Niveau d'eau (m)",
        "Water Level (m)",
        "Niveau d'eau (m)",
        "Value",
        "value",
    )
    fields = list(reader.fieldnames)
    time_col = next((k for k in time_keys if k in fields), fields[0])
    level_col = next((k for k in level_keys if k in fields), None)
    if level_col is None:
        for f in fields:
            fl = f.lower()
            if "level" in fl or "niveau" in fl:
                level_col = f
                break
    if level_col is None:
        logger.warning("no water level column in CSV; fields=%s", fields)
        return [], []

    values: list[float] = []
    times: list[datetime] = []
    for row in reader:
        raw_v = (row.get(level_col) or "").strip()
        raw_t = (row.get(time_col) or "").strip()
        if not raw_v or not raw_t:
            continue
        try:
            v = float(raw_v)
        except ValueError:
            continue
        try:
            dt = datetime.fromisoformat(raw_t.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        except ValueError:
            continue
        values.append(v)
        times.append(dt)
    return values, times
