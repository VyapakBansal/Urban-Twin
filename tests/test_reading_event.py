"""Unit tests for ReadingEvent schema."""

from datetime import datetime, timezone

from urban_twin.db.models import ReadingType
from urban_twin.messaging.schemas import ReadingEvent


def test_reading_event_roundtrip_json():
    event = ReadingEvent(
        station_id="calgary-kensington-1",
        lon=-114.081,
        lat=51.053,
        reading_type=ReadingType.TEMP,
        value=20.34,
        unit="C",
        recorded_at=datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
        source="weather",
        reading_id=42,
    )
    payload = event.model_dump(mode="json")
    restored = ReadingEvent.model_validate(payload)
    assert restored.reading_type == ReadingType.TEMP
    assert restored.reading_id == 42
    assert restored.value == 20.34
    assert restored.source == "weather"
