"""
detect.py
---------
SAR Oil-Spill Detection MVP  (Member 3 module — ai/sar/)

Pipeline:
    Load SAR image
        -> Preprocess (denoise)
        -> Threshold dark regions (candidate oil/look-alike areas)
        -> Clean up noise (morphology)
        -> Find significant connected region(s)
        -> Score candidates by shape (oil slicks tend to be elongated,
           irregular; pure sensor/low-wind artifacts tend to be small
           and more circular) to softly down-weight obvious look-alikes
        -> Pick best candidate, highlight it, compute confidence
        -> Save annotated output image + JSON result

This intentionally uses classical image processing (threshold +
morphology + contour shape analysis) rather than a trained deep model,
per the MVP rule: WORKING DEMO > COMPLEX MODEL. The `detect_spill()`
function is written so the thresholding/scoring step can later be
swapped for a trained segmentation model (e.g. U-Net) without changing
the rest of the pipeline (i/o, output image, JSON contract).

Usage:
    python detect.py
    python detect.py --image path/to/image.png
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np

# ---------------------------------------------------------------------
# Demo-only metadata. In the real system this would come from the
# satellite scene's geolocation metadata, not be invented from the
# image itself.
# ---------------------------------------------------------------------
DEMO_LATITUDE = 13.10
DEMO_LONGITUDE = 80.30


def load_image(path):
    """Load an image as grayscale. Returns None if it can't be read."""
    if not os.path.exists(path):
        return None
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return img  # None if OpenCV couldn't decode it


def preprocess(img):
    """Light denoising while preserving slick edges."""
    # Median blur suppresses speckle noise (typical of SAR) without
    # smearing region boundaries as much as a Gaussian blur would.
    denoised = cv2.medianBlur(img, 5)
    return denoised


def candidate_mask(img):
    """
    Threshold the image to find dark regions (low radar backscatter),
    which are candidates for oil slicks OR look-alikes.
    """
    # Otsu's method picks a data-driven threshold instead of a fixed
    # constant, so it adapts a bit to each image's brightness/contrast.
    _, mask = cv2.threshold(
        img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # Morphological open/close to remove speckle-sized noise and
    # fill small holes inside a candidate region.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return mask


def score_contour(contour, img_area, img, mask):
    """
    Score a candidate dark region on how "oil-slick-like" it looks,
    versus a small/simple look-alike artifact.

    This is a heuristic stand-in for what a trained classifier would
    do. Real oil slicks tend to be:
      - reasonably large relative to typical look-alikes
      - elongated / irregular (wind & current streaking), i.e. NOT a
        near-perfect circle
      - have a non-trivial perimeter-to-area ratio (rough boundary)

    Returns a dict with the raw metrics plus a 0-1 "oil_likelihood".
    """
    area = cv2.contourArea(contour)
    if area <= 0:
        return None

    perimeter = cv2.arcLength(contour, True)
    x, y, w, h = cv2.boundingRect(contour)

    # Elongation: how far the bounding box is from square/circular.
    aspect_ratio = max(w, h) / max(1, min(w, h))

    # Circularity: 1.0 = perfect circle, lower = more irregular.
    circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 1.0
    circularity = min(circularity, 1.0)

    area_fraction = area / img_area

    # Contrast check: a real dark slick/patch should be noticeably
    # darker than the surrounding sea, not just "whichever half Otsu
    # happened to split a noisy image into". This is what prevents
    # pure speckle noise from being called a detection.
    region_mask = np.zeros(img.shape, dtype=np.uint8)
    cv2.drawContours(region_mask, [contour], -1, 255, -1)
    outside_mask = cv2.bitwise_not(mask)  # everything NOT flagged as dark anywhere
    inside_mean = cv2.mean(img, mask=region_mask)[0]
    if cv2.countNonZero(outside_mask) > 0:
        outside_mean = cv2.mean(img, mask=outside_mask)[0]
    else:
        outside_mean = float(np.mean(img))
    contrast = outside_mean - inside_mean  # positive = region is darker than background
    contrast_score = np.clip(contrast / 25.0, 0, 1)

    # A region covering most of the frame is almost certainly a bad
    # threshold split, not a localized slick — heavily penalize it
    # rather than reward it for "size".
    plausible_extent = area_fraction <= 0.20

    # --- Heuristic scoring (weights chosen for a readable demo, not
    # a validated model) ---
    size_score = np.clip(area_fraction / 0.03, 0, 1)          # bigger -> more oil-like, saturates ~3% of frame
    elongation_score = np.clip((aspect_ratio - 1.0) / 2.0, 0, 1)  # more elongated -> more oil-like
    irregularity_score = np.clip(1.0 - circularity, 0, 1)      # less circular -> more oil-like

    oil_likelihood = float(
        0.35 * size_score
        + 0.20 * elongation_score
        + 0.15 * irregularity_score
        + 0.30 * contrast_score
    )
    if not plausible_extent:
        oil_likelihood *= 0.15  # near-zero out implausibly huge "regions"

    return {
        "area_px": float(area),
        "area_fraction": float(area_fraction),
        "aspect_ratio": float(aspect_ratio),
        "circularity": float(circularity),
        "oil_likelihood": oil_likelihood,
        "contrast": float(contrast),
        "bbox": (int(x), int(y), int(w), int(h)),
    }


def detect_spill(img):
    """
    Run the full detection pipeline on a grayscale image.

    Returns:
        result (dict): detection result (see build_result_json)
        annotated (np.ndarray): BGR image with detected region highlighted
        all_candidates (list): scored info for every candidate region found
    """
    pre = preprocess(img)
    mask = candidate_mask(pre)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_area = img.shape[0] * img.shape[1]

    # Ignore tiny specks — not a serious candidate region at all.
    min_area = img_area * 0.0015
    candidates = []
    for c in contours:
        info = score_contour(c, img_area, img, mask)
        if info is None:
            continue
        if info["area_px"] < min_area:
            continue
        info["contour"] = c
        candidates.append(info)

    annotated = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    if not candidates:
        return (
            {"detected": False, "confidence": 0.0, "reason": "no_significant_dark_region"},
            annotated,
            [],
        )

    # Pick the candidate with the highest oil_likelihood as the primary
    # detection (rather than simply the largest dark region), so an
    # obvious look-alike doesn't automatically win just for being big.
    candidates.sort(key=lambda c: c["oil_likelihood"], reverse=True)
    best = candidates[0]

    # Draw all candidates faintly, best one highlighted clearly.
    for c in candidates[1:]:
        cv2.drawContours(annotated, [c["contour"]], -1, (0, 200, 255), 1)
        x, y, w, h = c["bbox"]
        cv2.putText(
            annotated, "look-alike?", (x, max(0, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1, cv2.LINE_AA,
        )

    cv2.drawContours(annotated, [best["contour"]], -1, (0, 0, 255), 2)
    x, y, w, h = best["bbox"]
    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 0, 255), 1)
    cv2.putText(
        annotated,
        f"possible spill ({best['oil_likelihood']*100:.0f}%)",
        (x, max(0, y - 10)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA,
    )

    # Detection decision: require both a minimum oil-likelihood AND a
    # minimum contrast against the background. The contrast gate is
    # what separates a real dark patch from a handful of noise pixels
    # that happened to fall on the "dark" side of Otsu's threshold
    # (speckle noise has low contrast; a real slick/look-alike does not).
    MIN_CONTRAST = 15.0
    detected = best["oil_likelihood"] >= 0.35 and best["contrast"] >= MIN_CONTRAST

    result = {
        "detected": bool(detected),
        "confidence": round(best["oil_likelihood"], 2),
        "contrast_vs_background": round(best["contrast"], 1),
        "area_fraction_of_scene": round(best["area_fraction"], 4),
        "aspect_ratio": round(best["aspect_ratio"], 2),
        "num_candidate_regions": len(candidates),
    }

    return result, annotated, candidates


def build_result_json(pipeline_result):
    """Attach demo lat/lon metadata to the pipeline's detection result."""
    out = {
        "detected": pipeline_result.get("detected", False),
        "latitude": DEMO_LATITUDE,
        "longitude": DEMO_LONGITUDE,
        "confidence": pipeline_result.get("confidence", 0.0),
    }
    # Include extra diagnostic fields too (useful for debugging /
    # for the drift & AIS modules downstream), without breaking the
    # simple {detected, latitude, longitude, confidence} contract.
    extra = {k: v for k, v in pipeline_result.items() if k not in out}
    out.update(extra)
    return out


def main():
    parser = argparse.ArgumentParser(description="SAR oil-spill detection MVP")
    parser.add_argument(
        "--image",
        default=os.path.join(os.path.dirname(__file__), "sample_sar.png"),
        help="Path to a SAR image (grayscale works best). Defaults to the bundled sample.",
    )
    parser.add_argument(
        "--outdir",
        default=os.path.join(os.path.dirname(__file__), "output"),
        help="Directory to write the annotated image + JSON result.",
    )
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    img = load_image(args.image)
    if img is None:
        print(f"❌ Could not read image: {args.image}")
        print("   Check that the file exists and is a valid image format (png/jpg/tif).")
        sys.exit(1)

    if img.size == 0:
        print(f"❌ Image at {args.image} is empty/invalid.")
        sys.exit(1)

    try:
        pipeline_result, annotated, candidates = detect_spill(img)
    except Exception as e:  # keep the MVP from crashing ungracefully
        print(f"❌ Detection failed unexpectedly: {e}")
        sys.exit(1)

    result_json = build_result_json(pipeline_result)

    # Save annotated output image
    out_img_path = os.path.join(args.outdir, "detected_spill.png")
    cv2.imwrite(out_img_path, annotated)

    # Save JSON result
    out_json_path = os.path.join(args.outdir, "result.json")
    with open(out_json_path, "w") as f:
        json.dump(result_json, f, indent=2)

    # Console summary
    print("=" * 50)
    if result_json["detected"]:
        print("Possible oil spill detected")
    else:
        print("No significant oil spill detected")
    print(f"Confidence: {result_json['confidence'] * 100:.0f}%")
    print(f"Latitude:   {result_json['latitude']}")
    print(f"Longitude:  {result_json['longitude']}")
    print(f"Candidate regions found: {result_json.get('num_candidate_regions', 0)}")
    print("=" * 50)
    print(f"Annotated image saved to: {out_img_path}")
    print(f"JSON result saved to:     {out_json_path}")
    print(json.dumps(result_json, indent=2))


if __name__ == "__main__":
    main()
