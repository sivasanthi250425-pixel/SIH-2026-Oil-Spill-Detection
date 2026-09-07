"""Deterministic, simplified oil-drift simulation for the attribution MVP."""

from __future__ import annotations

import math
from typing import Dict, Tuple

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(p2)
    y = (
        math.cos(p1) * math.sin(p2)
        - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    )
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angular_difference_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _velocity(speed_knots: float, heading_deg: float) -> Tuple[float, float]:
    """Return east/north velocity in km/h."""
    speed_kmh = speed_knots * 1.852
    heading = math.radians(heading_deg)
    return speed_kmh * math.sin(heading), speed_kmh * math.cos(heading)


def drift_velocity(
    current_speed_knots: float,
    current_heading_deg: float,
    wind_speed_knots: float,
    wind_heading_deg: float,
    windage_factor: float = 0.03,
) -> Tuple[float, float]:
    """
    Demo oil velocity = surface current + small windage component.

    This is deliberately deterministic and is NOT an operational ocean model.
    """
    cx, cy = _velocity(current_speed_knots, current_heading_deg)
    wx, wy = _velocity(wind_speed_knots, wind_heading_deg)
    return cx + windage_factor * wx, cy + windage_factor * wy


def move_by_vector(
    lat: float, lon: float, east_kmh: float, north_kmh: float, hours: float
) -> Tuple[float, float]:
    """Local tangent-plane approximation for the small MVP search area."""
    km_per_degree_lat = 111.32
    km_per_degree_lon = 111.32 * max(math.cos(math.radians(lat)), 0.1)
    return (
        lat + north_kmh * hours / km_per_degree_lat,
        lon + east_kmh * hours / km_per_degree_lon,
    )


def simulate(
    source_lat: float,
    source_lon: float,
    hours: float,
    environment: Dict[str, float],
) -> Dict:
    east, north = drift_velocity(
        environment["current_speed_knots"],
        environment["current_heading_deg"],
        environment["wind_speed_knots"],
        environment["wind_heading_deg"],
        environment.get("windage_factor", 0.03),
    )
    predicted_lat, predicted_lon = move_by_vector(
        source_lat, source_lon, east, north, hours
    )
    direction = (math.degrees(math.atan2(east, north)) + 360.0) % 360.0

    return {
        "model": "simplified_constant_current_plus_windage",
        "valid": hours > 0,
        "hours_elapsed": round(hours, 2),
        "drift_velocity_kmh": {
            "east": round(east, 3),
            "north": round(north, 3),
        },
        "drift_direction_deg": round(direction, 1),
        "predicted_oil_position": {
            "latitude": round(predicted_lat, 6),
            "longitude": round(predicted_lon, 6),
        },
    }
