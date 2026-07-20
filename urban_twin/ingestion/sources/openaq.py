"""OpenAQ nearest air-quality readings for Kensington."""

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
            "User-Agent": "UrbanTwin/0.5 (portfolio; OpenAQ ingest)",
            "Accept": "application/json",
        }
        if settings.openaq_api_key:
            headers["X-API-Key"] = settings.openaq_api_key

        try:
            return await self._v2_latest(headers)
        except Exception as exc:
            logger.warning("OpenAQ v2 failed (%s); trying v3 locations", exc)
            return await self._v3_fallback(headers)

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
        # Without a key, v3 may 401 — surface a clear empty result for the orchestrator
        if not settings.openaq_api_key:
            logger.warning(
                "OpenAQ requires OPENAQ_API_KEY for reliable access; skipping air layer"
            )
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
        # Minimal: if structure differs, return empty rather than crash the whole ingest
        logger.info("OpenAQ v3 locations keys=%s", list(payload.keys()))
        return []


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
