"""
make_sample.py
---------------
Generates a synthetic demo SAR-like image (sample_sar.png) for the
oil-spill detection MVP, since no real SAR scene was supplied.

This is ONLY for demo purposes. It simulates:
  - a grey speckled sea background (SAR speckle noise)
  - a dark, elongated blob resembling an oil slick
  - a smaller, more circular dark patch resembling a "look-alike"
    (e.g. a low-wind area / biogenic film) to show the detector
    isn't naive

Run once to (re)create ai/sar/sample_sar.png:
    python make_sample.py
"""

import numpy as np
import cv2


def make_sar_sample(path="sample_sar.png", size=(512, 512), seed=42):
    rng = np.random.default_rng(seed)

    h, w = size
    # Base sea surface: mid-grey with speckle noise (typical SAR look)
    base = np.full((h, w), 120, dtype=np.float32)
    speckle = rng.normal(0, 18, size=(h, w))
    img = base + speckle

    # --- Simulated oil slick: dark, elongated, irregular blob ---
    slick_mask = np.zeros((h, w), dtype=np.uint8)
    center = (300, 260)
    axes = (90, 40)
    angle = 35
    cv2.ellipse(slick_mask, center, axes, angle, 0, 360, 255, -1)
    # add irregular "tail" to make it look wind/current-streaked
    cv2.ellipse(slick_mask, (360, 300), (50, 18), 20, 0, 360, 255, -1)
    cv2.ellipse(slick_mask, (400, 320), (30, 12), 15, 0, 360, 255, -1)
    slick_mask = cv2.GaussianBlur(slick_mask, (15, 15), 0)

    # Oil darkens backscatter significantly
    img = img - (slick_mask.astype(np.float32) / 255.0) * 70

    # --- Simulated "look-alike" patch (e.g. low-wind area), smaller & more circular ---
    lookalike_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(lookalike_mask, (140, 120), 22, 255, -1)
    lookalike_mask = cv2.GaussianBlur(lookalike_mask, (9, 9), 0)
    img = img - (lookalike_mask.astype(np.float32) / 255.0) * 35

    img = np.clip(img, 0, 255).astype(np.uint8)
    cv2.imwrite(path, img)
    print(f"Sample SAR-like demo image written to: {path}")


if __name__ == "__main__":
    make_sar_sample()
