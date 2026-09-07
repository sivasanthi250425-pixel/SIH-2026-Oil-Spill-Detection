from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# ── SAR Detection ──────────────────────────────────────────────

class SARImageRequest(BaseModel):
    image_url: str
    region: Optional[str] = None


class SpillDetection(BaseModel):
    detected: bool
    latitude: float
    longitude: float
    timestamp: str
    confidence: float
    area_sq_km: float
    severity: str


# ── Spill Analysis ─────────────────────────────────────────────

class SpillAnalyzeRequest(BaseModel):
    latitude: float
    longitude: float
    timestamp: str


class SpillAnalysis(BaseModel):
    latitude: float
    longitude: float
    timestamp: str
    confidence: float
    estimated_volume_tonnes: float
    wind_speed_knots: float
    current_speed_knots: float
    drift_direction_degrees: float
    affected_area_sq_km: float
    severity: str
    weather_conditions: str


# ── AIS Vessels ────────────────────────────────────────────────

class Vessel(BaseModel):
    vessel_id: str
    name: str
    imo: str
    ship_type: str
    flag: str
    length_m: float
    beam_m: float
    draft_m: float
    last_known_lat: float
    last_known_lon: float
    speed_knots: float
    course_degrees: float
    destination: str
    eta: str
    distance_to_spill_nm: float
    time_near_spill_hours: float


# ── Attribution ────────────────────────────────────────────────

class AttributeRequest(BaseModel):
    latitude: float
    longitude: float
    timestamp: str
    spill_confidence: float


class VesselAttribution(BaseModel):
    vessel_id: str
    vessel_name: str
    score: float
    confidence: str
    spatial_match: float
    temporal_match: float
    drift_consistency: float
    trajectory_match: float
    ais_reliability: float
    reason: str


class AttributionResponse(BaseModel):
    spill_location: dict
    candidates_found: int
    potential_source_vessel: VesselAttribution
    all_candidates: List[VesselAttribution]
