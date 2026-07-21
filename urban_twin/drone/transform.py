"""Local PX4 NED coordinates to WGS84 geodetic coordinates."""

from __future__ import annotations

import math
from dataclasses import dataclass

WGS84_A_M = 6_378_137.0
WGS84_E2 = 6.69437999014e-3


@dataclass(frozen=True)
class GeodeticPosition:
    lat: float
    lon: float
    altitude_m: float


def ned_to_wgs84(
    north_m: float,
    east_m: float,
    down_m: float,
    *,
    home_lat: float,
    home_lon: float,
    home_altitude_m: float,
) -> GeodeticPosition:
    """Convert a neighborhood-scale NED offset using WGS84 radii of curvature.

    This local tangent-plane approximation is sub-centimeter at the Urban Twin
    AOI scale and avoids treating latitude/longitude degrees as linear units.
    Altitudes use the same ellipsoid datum as the configured home altitude.
    """

    values = (north_m, east_m, down_m, home_lat, home_lon, home_altitude_m)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("NED transform values must be finite")
    if not -90.0 < home_lat < 90.0:
        raise ValueError("home latitude must be between -90 and 90")
    if not -180.0 <= home_lon <= 180.0:
        raise ValueError("home longitude must be between -180 and 180")

    lat_rad = math.radians(home_lat)
    sin_lat = math.sin(lat_rad)
    denominator = math.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    prime_vertical_radius = WGS84_A_M / denominator
    meridian_radius = (
        WGS84_A_M * (1.0 - WGS84_E2) / denominator**3
    )

    delta_lat = north_m / (meridian_radius + home_altitude_m)
    east_scale = (prime_vertical_radius + home_altitude_m) * math.cos(lat_rad)
    if abs(east_scale) < 1e-9:
        raise ValueError("NED transform is undefined at the poles")
    delta_lon = east_m / east_scale

    return GeodeticPosition(
        lat=home_lat + math.degrees(delta_lat),
        lon=home_lon + math.degrees(delta_lon),
        altitude_m=home_altitude_m - down_m,
    )

