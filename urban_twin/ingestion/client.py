import logging
from typing import Any

import httpx

OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"

# Prevent httpx from INFO-logging full request URLs (they include appid=...).
logging.getLogger("httpx").setLevel(logging.WARNING)


class OpenWeatherClient:
    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError(
                "OPENWEATHER_API_KEY is empty. Copy .env.example → .env and add your key."
            )
        self._api_key = api_key
        self._timeout = timeout

    async def fetch_current(self, lat: float, lon: float) -> dict[str, Any]:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self._api_key,
            "units": "metric",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(OPENWEATHER_CURRENT_URL, params=params)
            response.raise_for_status()
            return response.json()
