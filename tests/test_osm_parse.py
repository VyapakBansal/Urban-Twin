"""Unit tests for OSM Overpass → WKT conversion (no network)."""

from urban_twin.scripts.import_osm_buildings import elements_to_building_wkts


def test_elements_to_building_wkts_simple_square():
    payload = {
        "elements": [
            {"type": "node", "id": 1, "lat": 51.05, "lon": -114.08},
            {"type": "node", "id": 2, "lat": 51.05, "lon": -114.07},
            {"type": "node", "id": 3, "lat": 51.06, "lon": -114.07},
            {"type": "node", "id": 4, "lat": 51.06, "lon": -114.08},
            {
                "type": "way",
                "id": 10,
                "nodes": [1, 2, 3, 4, 1],
                "tags": {"building": "yes", "building:levels": "3"},
            },
        ]
    }
    result = elements_to_building_wkts(payload)
    assert len(result) == 1
    wkt, height = result[0]
    assert wkt.startswith("POLYGON((")
    assert height == 9.0
