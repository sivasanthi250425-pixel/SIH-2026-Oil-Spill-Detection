#!/usr/bin/env python3
"""
AIS + simplified drift + Potential Source Vessel ranking MVP.

Usage:
    python rank.py
    python rank.py --ais mock_ais.csv --output output.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from drift import (
    angular_difference_deg,
    bearing_deg,
    haversine_km,
    simulate,
)

WEIGHTS = {
    "spatial_match": 0.30,
    "temporal_match": 0.20,
    "drift_consistency": 0.25,
    "trajectory_match": 0.15,
    "ais_reliability": 0.10,
}

SPILL = {
    "latitude": 13.10,
    "longitude": 80.30,
    "timestamp": "2026-09-07T10:30:00",
}

ENVIRONMENT = {
    "current_speed_knots": 1.08,
    "current_heading_deg": 70.0,
    "wind_speed_knots": 5.0,
    "wind_heading_deg": 70.0,
    "windage_factor": 0.03,
}

CONFIG = {
    "candidate_radius_km": 45.0,
    "max_time_before_spill_hours": 18.0,
    "drift_tolerance_km": 12.0,
}


def parse_time(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def load_ais(path: Path) -> List[Dict]:
    vessels = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vessels.append(
                {
                    "vessel_id": row["vessel_id"],
                    "timestamp": row["timestamp"],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "speed": float(row["speed"]),
                    "heading": float(row["heading"]),
                    "ais_completeness": float(row.get("ais_completeness", 1.0)),
                    "position_accuracy": float(row.get("position_accuracy", 1.0)),
                }
            )
    return vessels


def candidate_filter(vessel: Dict) -> Dict:
    distance = haversine_km(
        vessel["latitude"], vessel["longitude"],
        SPILL["latitude"], SPILL["longitude"],
    )
    hours_before = (
        parse_time(SPILL["timestamp"]) - parse_time(vessel["timestamp"])
    ).total_seconds() / 3600.0

    relevant = (
        0.0 < hours_before <= CONFIG["max_time_before_spill_hours"]
        and distance <= CONFIG["candidate_radius_km"]
        and vessel["speed"] >= 1.0
    )
    return {
        "relevant": relevant,
        "distance_km": distance,
        "hours_before_spill": hours_before,
        "reason": (
            "within distance/time window and moving"
            if relevant
            else "outside distance/time/movement filter"
        ),
    }


def spatial_score(distance_km: float) -> float:
    return clamp(1.0 - distance_km / CONFIG["candidate_radius_km"])


def temporal_score(hours_before: float) -> float:
    # Best evidence is a plausible historical observation a few hours before
    # detection; very old observations decay toward zero.
    if hours_before <= 0:
        return 0.0
    ideal_hours = 5.0
    deviation = abs(hours_before - ideal_hours)
    return clamp(math.exp(-deviation / 8.0))


def drift_score(miss_km: float) -> float:
    return clamp(math.exp(-miss_km / CONFIG["drift_tolerance_km"]))


def trajectory_score(vessel: Dict) -> float:
    target_bearing = bearing_deg(
        vessel["latitude"], vessel["longitude"],
        SPILL["latitude"], SPILL["longitude"],
    )
    error = angular_difference_deg(vessel["heading"], target_bearing)
    return clamp(1.0 - error / 180.0)


def reliability_score(vessel: Dict) -> float:
    return clamp(
        0.60 * vessel["ais_completeness"]
        + 0.40 * vessel["position_accuracy"]
    )


def confidence(score: float) -> str:
    if score >= 0.80:
        return "High"
    if score >= 0.60:
        return "Medium"
    return "Low"


def reason_for(
    components: Dict[str, float],
    distance_km: float,
    miss_km: float,
) -> str:
    strengths = sorted(components.items(), key=lambda x: x[1], reverse=True)
    labels = {
        "spatial_match": "spatial",
        "temporal_match": "temporal",
        "drift_consistency": "drift",
        "trajectory_match": "trajectory",
        "ais_reliability": "AIS reliability",
    }
    strong = [labels[k] for k, v in strengths if v >= 0.75][:3]
    weak = [labels[k] for k, v in strengths[::-1] if v < 0.55][:2]

    if strong:
        msg = "Strong " + ", ".join(strong) + " agreement"
    else:
        msg = "Limited agreement across the evidence factors"
    if weak:
        msg += "; weaker evidence: " + ", ".join(weak)
    msg += f". Simulated oil miss distance: {miss_km:.1f} km."
    return msg


def score_vessel(vessel: Dict, filter_info: Dict) -> Dict:
    simulation = simulate(
        vessel["latitude"],
        vessel["longitude"],
        filter_info["hours_before_spill"],
        ENVIRONMENT,
    )
    predicted = simulation["predicted_oil_position"]
    miss_km = haversine_km(
        predicted["latitude"], predicted["longitude"],
        SPILL["latitude"], SPILL["longitude"],
    )

    components = {
        "spatial_match": spatial_score(filter_info["distance_km"]),
        "temporal_match": temporal_score(filter_info["hours_before_spill"]),
        "drift_consistency": drift_score(miss_km),
        "trajectory_match": trajectory_score(vessel),
        "ais_reliability": reliability_score(vessel),
    }

    weighted = {
        key: components[key] * WEIGHTS[key]
        for key in WEIGHTS
    }
    final_score = sum(weighted.values())

    target_bearing = bearing_deg(
        vessel["latitude"], vessel["longitude"],
        SPILL["latitude"], SPILL["longitude"],
    )

    return {
        "vessel_id": vessel["vessel_id"],
        "score": round(final_score, 4),
        "score_percent": round(final_score * 100, 2),
        "confidence": confidence(final_score),
        "evidence": {
            key: round(value, 4)
            for key, value in components.items()
        },
        "weighted_contribution": {
            key: round(value, 4)
            for key, value in weighted.items()
        },
        "reason": reason_for(
            components,
            filter_info["distance_km"],
            miss_km,
        ),
        "candidate_filter": {
            "distance_km": round(filter_info["distance_km"], 2),
            "hours_before_spill": round(filter_info["hours_before_spill"], 2),
            "relevant": True,
        },
        "trajectory": {
            "vessel_heading_deg": vessel["heading"],
            "source_to_spill_bearing_deg": round(target_bearing, 1),
            "heading_error_deg": round(
                angular_difference_deg(vessel["heading"], target_bearing), 1
            ),
        },
        "what_if_drift": {
            **simulation,
            "predicted_miss_distance_km": round(miss_km, 2),
        },
        "ais_observation": {
            "timestamp": vessel["timestamp"],
            "latitude": vessel["latitude"],
            "longitude": vessel["longitude"],
            "speed_knots": vessel["speed"],
            "heading_deg": vessel["heading"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ais",
        default=str(Path(__file__).with_name("mock_ais.csv")),
        help="Path to historical/mock AIS CSV",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).with_name("output.json")),
        help="JSON output path",
    )
    args = parser.parse_args()

    vessels = load_ais(Path(args.ais))
    filtered = []
    rejected = []

    for vessel in vessels:
        info = candidate_filter(vessel)
        if info["relevant"]:
            filtered.append(score_vessel(vessel, info))
        else:
            rejected.append(
                {
                    "vessel_id": vessel["vessel_id"],
                    "distance_km": round(info["distance_km"], 2),
                    "hours_before_spill": round(info["hours_before_spill"], 2),
                    "reason": info["reason"],
                }
            )

    filtered.sort(key=lambda item: item["score"], reverse=True)
    for index, item in enumerate(filtered, start=1):
        item["rank"] = index

    result = {
        "schema_version": "1.0",
        "analysis": {
            "type": "AIS + simplified drift Potential Source Vessel ranking",
            "status": "MVP / demonstration",
            "important_notice": (
                "Scores indicate evidence strength only. They do not establish "
                "legal responsibility or prove that a vessel caused a spill."
            ),
        },
        "spill": SPILL,
        "drift_model": {
            **ENVIRONMENT,
            "description": (
                "Deterministic demo model: constant surface current plus "
                "small windage component."
            ),
            "scientific_accuracy": "Not intended for operational ocean forecasting.",
        },
        "candidate_filter": {
            "candidate_radius_km": CONFIG["candidate_radius_km"],
            "max_time_before_spill_hours": CONFIG["max_time_before_spill_hours"],
            "input_vessels": len(vessels),
            "relevant_candidates": len(filtered),
            "rejected_candidates": rejected,
        },
        "scoring_weights": {
            "spatial_match": 0.30,
            "temporal_match": 0.20,
            "drift_consistency": 0.25,
            "trajectory_match": 0.15,
            "ais_reliability": 0.10,
        },
        "ranked_vessels": filtered,
        "highest_ranked_potential_source_vessel": (
            filtered[0]["vessel_id"] if filtered else None
        ),
    }

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
