"""Read-only geometry and association helpers for Phase 16 validation."""
from __future__ import annotations

from math import atan2, degrees, hypot
from typing import Iterable

import numpy as np


def pixel_motion(a: tuple[float, float], b_registered: tuple[float, float]) -> dict[str, float]:
    """Return the A-frame displacement; PA is east of north in pixel coordinates."""
    dx, dy = b_registered[0] - a[0], b_registered[1] - a[1]
    return {"dx_px": dx, "dy_px": dy, "distance_px": hypot(dx, dy),
            "position_angle_deg": (degrees(atan2(dx, dy)) + 360.0) % 360.0}


def angular_difference_deg(a: float, b: float) -> float:
    """Smallest signed angular difference, in degrees."""
    return (a - b + 180.0) % 360.0 - 180.0


def association_class(negative_distance_px: float | None, positive_distance_px: float | None,
                      vector_angle_error_deg: float | None, tolerance_px: float,
                      orientation_tolerance_deg: float) -> str:
    """Apply the preregistered, all-components association rule."""
    if negative_distance_px is None or positive_distance_px is None:
        return "NOT_EVALUABLE"
    negative_ok, positive_ok = negative_distance_px <= tolerance_px, positive_distance_px <= tolerance_px
    orientation_ok = vector_angle_error_deg is not None and vector_angle_error_deg <= orientation_tolerance_deg
    if negative_ok and positive_ok and orientation_ok:
        return "CONSISTENT"
    if negative_ok or positive_ok:
        return "PARTIAL"
    return "NOT_ASSOCIATED"


def nearest_pair(candidates: Iterable[dict], expected_negative: tuple[float, float],
                 expected_positive: tuple[float, float]) -> tuple[dict | None, float | None, float | None]:
    """Select the diagnostic nearest complete detector pair, without reranking it."""
    best, best_metric, best_neg, best_pos = None, None, None, None
    for candidate in candidates:
        neg, pos = candidate["negative"], candidate["positive"]
        neg_d = hypot(float(neg["x"]) - expected_negative[0], float(neg["y"]) - expected_negative[1])
        pos_d = hypot(float(pos["x"]) - expected_positive[0], float(pos["y"]) - expected_positive[1])
        metric = hypot(neg_d, pos_d)
        if best_metric is None or metric < best_metric:
            best, best_metric, best_neg, best_pos = candidate, metric, neg_d, pos_d
    return best, best_neg, best_pos


def sampled_finite(image: np.ndarray, x: float, y: float) -> bool:
    """A deterministic nearest-pixel data-validity check; it does not repair data."""
    ix, iy = int(round(x)), int(round(y))
    return bool(0 <= iy < image.shape[0] and 0 <= ix < image.shape[1] and np.isfinite(image[iy, ix]))
