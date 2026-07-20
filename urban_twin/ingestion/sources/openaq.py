"""Air quality ingest: OpenAQ when available, Open-Meteo PM2.5 fallback."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from urban_twin.config import settings
from urban_twin.db.models import ReadingType
from urban_twin.ingestion.normalize import NormalizedReading

logger = logging.getLogger(__name__)

OPENAQ_V3 = "https://api.openaq.org/v3/locations"
OPENAQ_V2 = "https://api.openaq.org/v2/latest"


class AirQualitySource:
    name = "air"

    async def fetch_readings(self) -> list[NormalizedReading]:
        headers = {
            "User-Agent": "UrbanTwin/0.5 (air-quality ingest)",
            "Accept": "application/json",
        }
        if settings.openaq_api_key:
            headers["X-API-Key"] = settings.openaq_api_key

        try:
            return await self._v2_latest(headers)
        except Exception as exc:
            logger.warning("OpenAQ v2 unavailable (%s); trying v3", exc)

        try:
            rows = await self._v3_fallback(headers)
            if rows:
                return rows
        except Exception as exc:
            logger.warning("OpenAQ v3 unavailable (%s); using Open-Meteo PM2.5", exc)

        return await self._open_meteo_pm25()

    async def _v2_latest(self, headers: dict[str, str]) -> list[NormalizedReading]:
        params = {
            "coordinates": f"{settings.station_lat},{settings.station_lon}",
            "radius": 25000,
            "limit": 5,
        }
        async with httpx.AsyncClient(timeout=45.0, headers=headers) as client:
            resp = await client.get(OPENAQ_V2, params=params)
            resp.raise_for_status()
            payload = resp.json()

        results = payload.get("results") or []
        if not results:
            raise ValueError("OpenAQ returned no nearby stations")

        station = results[0]
        lon = float(station.get("coordinates", {}).get("longitude", settings.station_lon))
        lat = float(station.get("coordinates", {}).get("latitude", settings.station_lat))
        station_id = f"openaq-{station.get('location') or station.get('id') or 'nearest'}"
        station_id = station_id[:60]

        out: list[NormalizedReading] = []
        for m in station.get("measurements") or []:
            param = str(m.get("parameter", "")).lower()
            value = m.get("value")
            if value is None:
                continue
            unit = str(m.get("unit") or "ug/m3")
            recorded_at = _parse_ts(m.get("lastUpdated") or m.get("date", {}).get("utc"))
            if param in ("pm25", "pm2.5"):
                out.append(
                    NormalizedReading(
                        station_id=station_id,
                        lon=lon,
                        lat=lat,
                        reading_type=ReadingType.AQI_PM25,
                        value=float(value),
                        unit=unit,
                        recorded_at=recorded_at,
                        source="openaq",
                    )
                )
            elif param in ("pm10",):
                out.append(
                    NormalizedReading(
                        station_id=station_id,
                        lon=lon,
                        lat=lat,
                        reading_type=ReadingType.AQI_PM10,
                        value=float(value),
                        unit=unit,
                        recorded_at=recorded_at,
                        source="openaq",
                    )
                )
        if not out:
            raise ValueError("OpenAQ station had no pm25/pm10 measurements")
        return out

    async def _v3_fallback(self, headers: dict[str, str]) -> list[NormalizedReading]:
        if not settings.openaq_api_key:
            return []
        params = {
            "coordinates": f"{settings.station_lon},{settings.station_lat}",
            "radius": 25000,
            "limit": 5,
        }
        async with httpx.AsyncClient(timeout=45.0, headers=headers) as client:
            resp = await client.get(OPENAQ_V3, params=params)
            resp.raise_for_status()
            payload = resp.json()
        logger.info("OpenAQ v3 locations keys=%s", list(payload.keys()))
        return []

    async def _open_meteo_pm25(self) -> list[NormalizedReading]:
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": settings.station_lat,
            "longitude": settings.station_lon,
            "current": "pm2_5",
            "timezone": "UTC",
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        cur = data.get("current") or {}
        value = cur.get("pm2_5")
        if value is None:
            logger.warning("Open-Meteo air quality returned no pm2_5")
            return []
        recorded = _parse_ts(cur.get("time"))
        return [
            NormalizedReading(
                station_id=f"openmeteo-aq-{settings.station_id}"[:60],
                lon=settings.station_lon,
                lat=settings.station_lat,
                reading_type=ReadingType.AQI_PM25,
                value=float(value),
                unit="ug/m3",
                recorded_at=recorded,
                source="open-meteo",
            )
        ]


def _parse_ts(raw: Any) -> datetime:
    if raw is None:
        return datetime.now(timezone.utc)
    text = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
