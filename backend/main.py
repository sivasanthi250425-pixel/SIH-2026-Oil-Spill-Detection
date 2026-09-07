from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from models import (
    SARImageRequest,
    SpillDetection,
    SpillAnalyzeRequest,
    SpillAnalysis,
    Vessel,
    AttributeRequest,
    AttributionResponse,
    VesselAttribution,
)

app = FastAPI(
    title="Oil Spill Detection & Vessel Attribution API",
    description="SIH 2026 MVP - SAR-based oil spill detection with AIS vessel attribution",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Mock Data ──────────────────────────────────────────────────

MOCK_SPILL = SpillDetection(
    detected=True,
    latitude=13.10,
    longitude=80.30,
    timestamp="2026-09-07T10:30:00",
    confidence=0.91,
    area_sq_km=4.2,
    severity="high",
)

MOCK_ANALYSIS = SpillAnalysis(
    latitude=13.10,
    longitude=80.30,
    timestamp="2026-09-07T10:30:00",
    confidence=0.91,
    estimated_volume_tonnes=35.0,
    wind_speed_knots=12.5,
    current_speed_knots=1.8,
    drift_direction_degrees=225.0,
    affected_area_sq_km=4.2,
    severity="high",
    weather_conditions="Partly cloudy, moderate wind",
)

MOCK_VESSELS = [
    Vessel(
        vessel_id="VES-001",
        name="MV Ocean Pioneer",
        imo="IMO9876543",
        ship_type="Crude Oil Tanker",
        flag="India",
        length_m=183.0,
        beam_m=32.2,
        draft_m=12.8,
        last_known_lat=13.12,
        last_known_lon=80.35,
        speed_knots=8.5,
        course_degrees=210.0,
        destination="Chennai",
        eta="2026-09-08T06:00:00",
        distance_to_spill_nm=1.8,
        time_near_spill_hours=2.5,
    ),
    Vessel(
        vessel_id="VES-002",
        name="MT Coastal Spirit",
        imo="IMO9876544",
        ship_type="Product Tanker",
        flag="Panama",
        length_m=140.0,
        beam_m=22.0,
        draft_m=9.5,
        last_known_lat=13.05,
        last_known_lon=80.25,
        speed_knots=6.2,
        course_degrees=195.0,
        destination="Visakhapatnam",
        eta="2026-09-07T22:00:00",
        distance_to_spill_nm=3.2,
        time_near_spill_hours=1.0,
    ),
    Vessel(
        vessel_id="VES-003",
        name="MV Northern Star",
        imo="IMO9876545",
        ship_type="Bulk Carrier",
        flag="Liberia",
        length_m=200.0,
        beam_m=32.0,
        draft_m=13.0,
        last_known_lat=13.20,
        last_known_lon=80.40,
        speed_knots=10.1,
        course_degrees=180.0,
        destination="Colombo",
        eta="2026-09-07T18:00:00",
        distance_to_spill_nm=7.5,
        time_near_spill_hours=0.0,
    ),
    Vessel(
        vessel_id="VES-004",
        name="MT Bay Watch",
        imo="IMO9876546",
        ship_type="Chemical Tanker",
        flag="Malta",
        length_m=105.0,
        beam_m=17.0,
        draft_m=6.8,
        last_known_lat=13.08,
        last_known_lon=80.32,
        speed_knots=4.8,
        course_degrees=220.0,
        destination="Kolkata",
        eta="2026-09-08T14:00:00",
        distance_to_spill_nm=1.4,
        time_near_spill_hours=3.0,
    ),
]

MOCK_ATTRIBUTION = AttributionResponse(
    spill_location={
        "latitude": 13.10,
        "longitude": 80.30,
        "timestamp": "2026-09-07T10:30:00",
    },
    candidates_found=4,
    potential_source_vessel=VesselAttribution(
        vessel_id="VES-001",
        vessel_name="MV Ocean Pioneer",
        score=0.87,
        confidence="high",
        spatial_match=0.92,
        temporal_match=0.85,
        drift_consistency=0.88,
        trajectory_match=0.84,
        ais_reliability=0.90,
        reason="Highest proximity (1.8 nm), present at spill time, trajectory aligns with drift model, crude oil tanker type consistent with spill signature.",
    ),
    all_candidates=[
        VesselAttribution(
            vessel_id="VES-001",
            vessel_name="MV Ocean Pioneer",
            score=0.87,
            confidence="high",
            spatial_match=0.92,
            temporal_match=0.85,
            drift_consistency=0.88,
            trajectory_match=0.84,
            ais_reliability=0.90,
            reason="Closest vessel at spill time, trajectory aligns with drift model, crude oil tanker type consistent with spill signature.",
        ),
        VesselAttribution(
            vessel_id="VES-004",
            vessel_name="MT Bay Watch",
            score=0.64,
            confidence="medium",
            spatial_match=0.88,
            temporal_match=0.70,
            drift_consistency=0.60,
            trajectory_match=0.55,
            ais_reliability=0.72,
            reason="Near spill location but lower drift consistency and trajectory match. Chemical tanker less likely source.",
        ),
        VesselAttribution(
            vessel_id="VES-002",
            vessel_name="MT Coastal Spirit",
            score=0.51,
            confidence="low",
            spatial_match=0.70,
            temporal_match=0.55,
            drift_consistency=0.45,
            trajectory_match=0.40,
            ais_reliability=0.65,
            reason="Moderate distance (3.2 nm), limited time in vicinity, trajectory partially matches.",
        ),
        VesselAttribution(
            vessel_id="VES-003",
            vessel_name="MV Northern Star",
            score=0.22,
            confidence="low",
            spatial_match=0.25,
            temporal_match=0.15,
            drift_consistency=0.20,
            trajectory_match=0.18,
            ais_reliability=0.80,
            reason="Far from spill (7.5 nm), not present at spill time, bulk carrier unlikely source.",
        ),
    ],
)


# ── Endpoints ──────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "Oil Spill Detection & Vessel Attribution API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.post("/detect-spill", response_model=SpillDetection)
def detect_spill(request: SARImageRequest):
    """
    Accept a SAR image reference and return oil spill detection results.
    Mock: always returns a positive detection at the sample location.
    """
    return MOCK_SPILL


@app.post("/analyze-spill", response_model=SpillAnalysis)
def analyze_spill(request: SpillAnalyzeRequest):
    """
    Analyze a detected spill: estimate volume, drift, weather, severity.
    Mock: returns analysis for the sample spill coordinates.
    """
    return MOCK_ANALYSIS


@app.get("/vessels", response_model=list[Vessel])
def get_vessels(
    lat: float = 13.10,
    lon: float = 80.30,
    radius_nm: float = 20.0,
):
    """
    Get AIS vessel candidates near a spill location within a radius (nautical miles).
    Mock: returns the 4 sample candidate vessels.
    """
    return MOCK_VESSELS


@app.post("/attribute", response_model=AttributionResponse)
def attribute_spill(request: AttributeRequest):
    """
    Run evidence-fusion attribution to rank candidate vessels.
    Returns a potential source vessel and scored candidates.
    Mock: returns ranked attribution results for the sample spill.
    """
    return MOCK_ATTRIBUTION
