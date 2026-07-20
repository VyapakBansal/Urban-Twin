"""OpenWeather current conditions → NormalizedReading list."""

from __future__ import annotations

from urban_twin.config import settings
from urban_twin.ingestion.client import OpenWeatherClient
from urban_twin.ingestion.normalize import NormalizedReading, normalize_openweather_current


class WeatherSource:
    name = "weather"

    async def fetch_readings(self) -> list[NormalizedReading]:
        client = OpenWeatherClient(settings.openweather_api_key)
        payload = await client.fetch_current(settings.station_lat, settings.station_lon)
        return normalize_openweather_current(
            payload,
            station_id=settings.station_id,
            lon=settings.station_lon,
            lat=settings.station_lat,
        )
