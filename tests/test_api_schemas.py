"""API schema / bbox parsing tests (no DB)."""

from datetime import datetime, timezone

import pytest

from urban_twin.api.schemas import BBoxParams, ReadingOut


def test_bbox_params_parsed():
    p = BBoxParams(bbox="-114.1,51.05,-114.06,51.06")
    assert p.parsed() == (-114.1, 51.05, -114.06, 51.06)


def test_bbox_params_invalid():
    p = BBoxParams(bbox="1,2,3")
    with pytest.raises(ValueError):
        p.parsed()


def test_reading_out_model():
    row = ReadingOut(
        id=1,
        station_id="calgary-kensington-1",
        reading_type="temp",
        value=20.0,
        unit="C",
        recorded_at=datetime.now(timezone.utc),
        lon=-114.081,
        lat=51.053,
    )
    assert row.reading_type == "temp"
