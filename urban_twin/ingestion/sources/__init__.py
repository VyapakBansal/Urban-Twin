"""Pluggable data-source ingest modules."""

from __future__ import annotations

from typing import Protocol

from urban_twin.ingestion.normalize import NormalizedReading


class ReadingSource(Protocol):
    name: str

    async def fetch_readings(self) -> list[NormalizedReading]:
        ...
