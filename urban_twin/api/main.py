"""FastAPI REST layer for historical / static queries."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from urban_twin.api.queries import (
    amenities_as_geojson,
    buildings_as_geojson,
    incidents_as_geojson,
    latest_forecasts,
    layer_counts,
    pathways_as_geojson,
    readings_query,
)
from urban_twin.api.schemas import (
    AmenityOut,
    BuildingOut,
    ForecastOut,
    HealthOut,
    IncidentOut,
    LayerCountsOut,
    PathwayOut,
    ReadingOut,
)
from urban_twin.config import settings
from urban_twin.db.session import get_async_session

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        parts = [float(p.strip()) for p in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("need 4 numbers")
        min_lon, min_lat, max_lon, max_lat = parts
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError("min must be < max")
        return min_lon, min_lat, max_lon, max_lat
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid bbox: {exc}") from exc


def create_app() -> FastAPI:
    app = FastAPI(
        title="Urban Twin API",
        description=(
            "REST surface for Kensington Calgary urban twin: "
            "buildings, sensor readings, and forecasts. "
            "Live push is on the WebSocket bridge (`/ws/live`), not here."
        ),
        version="0.3.0",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        """Browser-friendly landing — `/` is not a data endpoint."""
        return {
            "service": "urban-twin-api",
            "docs": "/docs",
            "health": "/health",
            "buildings": "/buildings",
            "readings": "/readings",
            "forecasts": "/forecasts",
            "layers": "/layers/pathways|/layers/amenities|/layers/incidents|/layers/counts",
        }

    @app.get("/health", response_model=HealthOut)
    async def health() -> HealthOut:
        return HealthOut()

    @app.get("/buildings", response_model=list[BuildingOut])
    @limiter.limit(settings.api_rate_limit)
    async def get_buildings(
        request: Request,
        bbox: str | None = Query(
            default=None,
            description="min_lon,min_lat,max_lon,max_lat (WGS84)",
            examples=["-114.100,51.048,-114.062,51.062"],
        ),
        limit: int = Query(default=5000, ge=1, le=20000),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[BuildingOut]:
        rows = await buildings_as_geojson(session, _parse_bbox(bbox), limit=limit)
        return [BuildingOut.model_validate(r) for r in rows]

    @app.get("/readings", response_model=list[ReadingOut])
    @limiter.limit(settings.api_rate_limit)
    async def get_readings(
        request: Request,
        station_id: str | None = None,
        reading_type: str | None = Query(
            default=None,
            description="temp | precip | wind | humidity | river_level | aqi_pm25 | …",
        ),
        source: str | None = Query(
            default=None,
            description="weather | river | openaq",
        ),
        from_: datetime | None = Query(default=None, alias="from"),
        to: datetime | None = None,
        limit: int = Query(default=500, ge=1, le=5000),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[ReadingOut]:
        if from_ and to and from_ > to:
            raise HTTPException(status_code=422, detail="'from' must be <= 'to'")
        rows = await readings_query(
            session,
            station_id=station_id,
            reading_type=reading_type,
            source=source,
            from_ts=from_,
            to_ts=to,
            limit=limit,
        )
        return [ReadingOut.model_validate(r) for r in rows]

    @app.get("/forecasts", response_model=list[ForecastOut])
    @limiter.limit(settings.api_rate_limit)
    async def get_forecasts(
        request: Request,
        station_id: str | None = None,
        reading_type: str | None = None,
        session: AsyncSession = Depends(get_async_session),
    ) -> list[ForecastOut]:
        rows = await latest_forecasts(
            session,
            station_id=station_id,
            reading_type=reading_type,
        )
        return [ForecastOut.model_validate(r) for r in rows]

    @app.get("/layers/counts", response_model=LayerCountsOut)
    @limiter.limit(settings.api_rate_limit)
    async def get_layer_counts(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
    ) -> LayerCountsOut:
        return LayerCountsOut.model_validate(await layer_counts(session))

    @app.get("/layers/pathways", response_model=list[PathwayOut])
    @limiter.limit(settings.api_rate_limit)
    async def get_pathways(
        request: Request,
        bbox: str | None = Query(default="-114.100,51.048,-114.062,51.062"),
        limit: int = Query(default=2000, ge=1, le=5000),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[PathwayOut]:
        rows = await pathways_as_geojson(session, _parse_bbox(bbox), limit=limit)
        return [PathwayOut.model_validate(r) for r in rows]

    @app.get("/layers/amenities", response_model=list[AmenityOut])
    @limiter.limit(settings.api_rate_limit)
    async def get_amenities(
        request: Request,
        bbox: str | None = Query(default="-114.100,51.048,-114.062,51.062"),
        limit: int = Query(default=2000, ge=1, le=5000),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[AmenityOut]:
        rows = await amenities_as_geojson(session, _parse_bbox(bbox), limit=limit)
        return [AmenityOut.model_validate(r) for r in rows]

    @app.get("/layers/incidents", response_model=list[IncidentOut])
    @limiter.limit(settings.api_rate_limit)
    async def get_incidents(
        request: Request,
        bbox: str | None = Query(default="-114.120,51.040,-114.050,51.070"),
        limit: int = Query(default=500, ge=1, le=2000),
        session: AsyncSession = Depends(get_async_session),
    ) -> list[IncidentOut]:
        rows = await incidents_as_geojson(session, _parse_bbox(bbox), limit=limit)
        return [IncidentOut.model_validate(r) for r in rows]

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()


def cli() -> None:
    parser = argparse.ArgumentParser(description="Urban Twin REST API")
    parser.add_argument("--host", default=settings.api_host)
    parser.add_argument("--port", type=int, default=settings.api_port)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    import uvicorn

    uvicorn.run(
        "urban_twin.api.main:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
