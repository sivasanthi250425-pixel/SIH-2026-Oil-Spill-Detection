# AIS + Drift + Potential Source Vessel Attribution MVP

## 1. What this module does

This module demonstrates the Member 4 attribution pipeline:

**Detected Spill -> Candidate Vessels -> What-if Drift Simulation -> Compare with Spill -> Evidence Score -> Vessel Ranking**

After a spill is detected, historical/mock AIS observations are filtered by distance, time, and vessel movement. Each relevant **Candidate Vessel** is then treated as a hypothetical source and a simplified oil-drift path is simulated from its AIS position to the spill observation time.

The module returns an explainable ranking of **Potential Source Vessels**.

> A ranking is evidence strength, not proof of legal responsibility.

## 2. Input data

### Spill

The MVP uses the requested mock spill:

- Latitude: `13.10`
- Longitude: `80.30`
- Timestamp: `2026-09-07T10:30:00`

### AIS

`mock_ais.csv` contains six historical/mock observations with:

- `vessel_id`
- `timestamp`
- `latitude`
- `longitude`
- `speed`
- `heading`
- `ais_completeness`
- `position_accuracy`

The last two fields are mock quality indicators used by the AIS reliability score.

## 3. How to run

No external Python packages are required; the implementation uses the Python standard library.

From this directory:

```bash
python rank.py
```

This writes:

```text
output.json
```

and also prints the JSON to the terminal.

To choose different input/output paths:

```bash
python rank.py --ais mock_ais.csv --output output.json
```

## 4. Candidate filtering

A vessel is considered relevant when:

1. Its AIS observation occurred before the spill observation.
2. It is no more than `45 km` from the detected spill.
3. Its observation is no more than `18 hours` before the spill.
4. Its speed is at least `1 knot`.

Obviously irrelevant observations are reported under `candidate_filter.rejected_candidates`.

## 5. What-if drift simulation

For every relevant candidate, the MVP asks:

> If this vessel released oil at its observed AIS position, where would the oil be at the spill observation time?

The demo model is:

`oil velocity = surface current + windage_factor × wind velocity`

The model assumes constant environmental conditions and uses a local tangent-plane approximation for movement.

This is intentionally deterministic and explainable. **It is not a scientifically validated ocean forecast and must not be used as an operational spill-response model.**

The JSON includes:

- simulated drift velocity
- drift direction
- predicted oil latitude/longitude
- distance between predicted oil position and observed spill

## 6. Evidence scoring

The final score is a weighted sum:

| Evidence | Weight |
|---|---:|
| Spatial match | 30% |
| Temporal match | 20% |
| Drift consistency | 25% |
| Trajectory match | 15% |
| AIS reliability | 10% |

Each component is normalized from `0.0` to `1.0`.

Confidence labels:

- `High`: score >= 0.80
- `Medium`: score >= 0.60
- `Low`: score < 0.60

The JSON exposes both raw component scores and weighted contributions so a dashboard can explain why a Candidate Vessel ranked where it did.

## 7. Example output

The generated `output.json` contains this overall structure:

```json
{
  "spill": {
    "latitude": 13.1,
    "longitude": 80.3,
    "timestamp": "2026-09-07T10:30:00"
  },
  "ranked_vessels": [
    {
      "vessel_id": "VESSEL_A",
      "score": 0.0,
      "score_percent": 0.0,
      "confidence": "Low",
      "evidence": {
        "spatial_match": 0.0,
        "temporal_match": 0.0,
        "drift_consistency": 0.0,
        "trajectory_match": 0.0,
        "ais_reliability": 0.0
      },
      "reason": "..."
    }
  ],
  "highest_ranked_potential_source_vessel": "VESSEL_A"
}
```

The numeric values above are placeholders for the structure; run `python rank.py` to generate the actual deterministic values.

## 8. Safety / interpretation

Use these terms in the UI and API:

- `Potential Source Vessel`
- `Highest-ranked Potential Source Vessel`
- `Candidate Vessel`
- `Confidence Score`

Do **not** describe a ranked vessel as "guilty", "the culprit", or "confirmed responsible". AIS and drift evidence can support investigation, but this MVP cannot make a definitive legal determination.
