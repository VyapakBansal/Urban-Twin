"""Geo helpers for API responses."""

from __future__ import annotations

import json
from typing import Any

from geoalchemy2 import functions as geo_func
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from urban_twin.db.models import Amenity, Building, Forecast, Incident, Pathway, SensorReading


async def buildings_as_geojson(
    session: AsyncSession,
    bbox: tuple[float, float, float, float] | None,
    *,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    geom_json = geo_func.ST_AsGeoJSON(Building.geometry)
    stmt: Select = select(
        Building.id,
        Building.height,
        Building.source,
        geom_json.label("geojson"),
    )
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = geo_func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        stmt = stmt.where(geo_func.ST_Intersects(Building.geometry, envelope))
    stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "height": r.height,
            "source": r.source,
            "geojson": json.loads(r.geojson),
        }
        for r in rows
    ]


async def readings_query(
    session: AsyncSession,
    *,
    station_id: str | None,
    reading_type: str | None,
    source: str | None,
    from_ts,
    to_ts,
    limit: int = 500,
) -> list[dict[str, Any]]:
    lon = geo_func.ST_X(SensorReading.geometry)
    lat = geo_func.ST_Y(SensorReading.geometry)
    stmt = select(
        SensorReading.id,
        SensorReading.station_id,
        SensorReading.source,
        SensorReading.reading_type,
        SensorReading.value,
        SensorReading.unit,
        SensorReading.recorded_at,
        lon.label("lon"),
        lat.label("lat"),
    ).order_by(SensorReading.recorded_at.desc())

    if station_id:
        stmt = stmt.where(SensorReading.station_id == station_id)
    if reading_type:
        stmt = stmt.where(SensorReading.reading_type == reading_type)
    if source:
        stmt = stmt.where(SensorReading.source == source)
    if from_ts:
        stmt = stmt.where(SensorReading.recorded_at >= from_ts)
    if to_ts:
        stmt = stmt.where(SensorReading.recorded_at <= to_ts)
    stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "station_id": r.station_id,
            "source": r.source,
            "reading_type": r.reading_type,
            "value": r.value,
            "unit": r.unit,
            "recorded_at": r.recorded_at,
            "lon": float(r.lon),
            "lat": float(r.lat),
        }
        for r in rows
    ]


async def latest_forecasts(
    session: AsyncSession,
    *,
    station_id: str | None,
    reading_type: str | None,
) -> list[dict[str, Any]]:
    """Return the newest forecast row per (station_id, reading_type)."""
    lon = geo_func.ST_X(Forecast.geometry)
    lat = geo_func.ST_Y(Forecast.geometry)
    stmt = select(
        Forecast.id,
        Forecast.station_id,
        Forecast.reading_type,
        Forecast.predicted_value,
        Forecast.target_time,
        Forecast.model_version,
        Forecast.generated_at,
        Forecast.notes,
        lon.label("lon"),
        lat.label("lat"),
    ).order_by(Forecast.generated_at.desc())

    if station_id:
        stmt = stmt.where(Forecast.station_id == station_id)
    if reading_type:
        stmt = stmt.where(Forecast.reading_type == reading_type)

    rows = (await session.execute(stmt)).all()
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        key = (r.station_id, r.reading_type)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": r.id,
                "station_id": r.station_id,
                "reading_type": r.reading_type,
                "predicted_value": r.predicted_value,
                "target_time": r.target_time,
                "model_version": r.model_version,
                "generated_at": r.generated_at,
                "notes": r.notes,
                "lon": float(r.lon),
                "lat": float(r.lat),
            }
        )
    return out


async def pathways_as_geojson(
    session: AsyncSession,
    bbox: tuple[float, float, float, float] | None,
    *,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    geom_json = geo_func.ST_AsGeoJSON(Pathway.geometry)
    stmt = select(
        Pathway.id,
        Pathway.name,
        Pathway.source,
        geom_json.label("geojson"),
    )
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = geo_func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        stmt = stmt.where(geo_func.ST_Intersects(Pathway.geometry, envelope))
    stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "source": r.source,
            "geojson": json.loads(r.geojson),
        }
        for r in rows
    ]


async def amenities_as_geojson(
    session: AsyncSession,
    bbox: tuple[float, float, float, float] | None,
    *,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    lon = geo_func.ST_X(Amenity.geometry)
    lat = geo_func.ST_Y(Amenity.geometry)
    stmt = select(
        Amenity.id,
        Amenity.name,
        Amenity.amenity_type,
        Amenity.source,
        lon.label("lon"),
        lat.label("lat"),
    )
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = geo_func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        stmt = stmt.where(geo_func.ST_Intersects(Amenity.geometry, envelope))
    stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "amenity_type": r.amenity_type,
            "source": r.source,
            "lon": float(r.lon),
            "lat": float(r.lat),
        }
        for r in rows
    ]


async def incidents_as_geojson(
    session: AsyncSession,
    bbox: tuple[float, float, float, float] | None,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    lon = geo_func.ST_X(Incident.geometry)
    lat = geo_func.ST_Y(Incident.geometry)
    stmt = select(
        Incident.id,
        Incident.external_id,
        Incident.description,
        Incident.started_at,
        Incident.source,
        lon.label("lon"),
        lat.label("lat"),
    ).order_by(Incident.started_at.desc().nullslast())
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        envelope = geo_func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        stmt = stmt.where(geo_func.ST_Intersects(Incident.geometry, envelope))
    stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "external_id": r.external_id,
            "description": r.description,
            "started_at": r.started_at,
            "source": r.source,
            "lon": float(r.lon),
            "lat": float(r.lat),
        }
        for r in rows
    ]


async def layer_counts(session: AsyncSession) -> dict[str, int]:
    from sqlalchemy import func

    buildings = await session.scalar(select(func.count()).select_from(Building))
    pathways = await session.scalar(select(func.count()).select_from(Pathway))
    amenities = await session.scalar(select(func.count()).select_from(Amenity))
    incidents = await session.scalar(select(func.count()).select_from(Incident))
    readings = await session.scalar(select(func.count()).select_from(SensorReading))
    return {
        "buildings": int(buildings or 0),
        "pathways": int(pathways or 0),
        "amenities": int(amenities or 0),
        "incidents": int(incidents or 0),
        "readings": int(readings or 0),
    }
