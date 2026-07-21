import pytest

from urban_twin.drone.transform import ned_to_wgs84


HOME = {
    "home_lat": 51.053,
    "home_lon": -114.081,
    "home_altitude_m": 1045.0,
}


def test_ned_origin_maps_to_configured_home():
    position = ned_to_wgs84(0.0, 0.0, 0.0, **HOME)
    assert position.lat == HOME["home_lat"]
    assert position.lon == HOME["home_lon"]
    assert position.altitude_m == HOME["home_altitude_m"]


def test_known_kensington_ned_offset_maps_to_wgs84():
    # WGS84 local-tangent reference: 100 m north, 100 m east, 20 m up.
    position = ned_to_wgs84(100.0, 100.0, -20.0, **HOME)
    assert position.lat == pytest.approx(51.0538987, abs=2e-7)
    assert position.lon == pytest.approx(-114.0795741, abs=3e-7)
    assert position.altitude_m == 1065.0


def test_ned_transform_rejects_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        ned_to_wgs84(float("nan"), 0.0, 0.0, **HOME)

