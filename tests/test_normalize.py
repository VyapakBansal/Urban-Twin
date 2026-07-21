from urban_twin.ingestion.normalize import normalize_openweather_current
from urban_twin.db.models import ReadingType


SAMPLE_PAYLOAD = {
    "coord": {"lon": -104.9825, "lat": 39.765},
    "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
    "main": {"temp": 22.5, "humidity": 40, "pressure": 1012},
    "wind": {"speed": 3.1, "deg": 180},
    "rain": {"1h": 0.2},
    "dt": 1721491200,
    "name": "Denver",
}


def test_normalize_openweather_current_all_types():
    readings = normalize_openweather_current(
        SAMPLE_PAYLOAD,
        station_id="calgary-kensington-1",
        lon=-114.081,
        lat=51.053,
    )
    by_type = {r.reading_type: r for r in readings}
    assert set(by_type) == {
        ReadingType.TEMP,
        ReadingType.HUMIDITY,
        ReadingType.WIND,
        ReadingType.WIND_DIR,
        ReadingType.PRECIP,
    }
    assert by_type[ReadingType.TEMP].value == 22.5
    assert by_type[ReadingType.TEMP].unit == "C"
    assert by_type[ReadingType.HUMIDITY].value == 40
    assert by_type[ReadingType.WIND].value == 3.1
    assert by_type[ReadingType.WIND_DIR].value == 180
    assert by_type[ReadingType.PRECIP].value == 0.2


def test_normalize_precip_defaults_to_zero():
    payload = {**SAMPLE_PAYLOAD}
    del payload["rain"]
    readings = normalize_openweather_current(
        payload,
        station_id="x",
        lon=0.0,
        lat=0.0,
    )
    precip = next(r for r in readings if r.reading_type == ReadingType.PRECIP)
    assert precip.value == 0.0
