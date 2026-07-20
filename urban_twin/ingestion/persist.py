from geoalchemy2.elements import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from urban_twin.db.models import SensorReading
from urban_twin.ingestion.normalize import NormalizedReading


async def write_readings(
    session: AsyncSession,
    readings: list[NormalizedReading],
) -> list[SensorReading]:
    rows: list[SensorReading] = []
    for r in readings:
        row = SensorReading(
            station_id=r.station_id,
            geometry=WKTElement(f"POINT({r.lon} {r.lat})", srid=4326),
            reading_type=r.reading_type.value,
            value=r.value,
            unit=r.unit,
            recorded_at=r.recorded_at,
        )
        session.add(row)
        rows.append(row)
    await session.commit()
    for row in rows:
        await session.refresh(row)
    return rows
