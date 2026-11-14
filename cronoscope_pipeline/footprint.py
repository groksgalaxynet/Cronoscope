"""Exact celestial-coordinate containment through a normalized image WCS.

Pixel support follows Astropy/NumPy's zero-based pixel-centre convention.  For
an image of width W and height H, the closed support is -0.5 <= x <= W - 0.5
and -0.5 <= y <= H - 0.5.  Thus edge pixel centres (0 and W-1) are interior.
RA is normalized with ``ra % 360`` after finite-number validation.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

import numpy as np

from .models import (ContainmentResult, ContainmentStatus, EphemerisMatch,
                     NormalizedFitsProduct, TemporalStatus, WcsStatus)

BOUNDARY_EPSILON_PX = 1e-6


def _unknown(product: NormalizedFitsProduct, status: ContainmentStatus, ra: float | None, dec: float | None,
             reason: str) -> ContainmentResult:
    shape = product.image_shape
    height = None if not shape or len(shape) != 2 else shape[0]
    width = None if not shape or len(shape) != 2 else shape[1]
    return ContainmentResult(status, None, ra, dec, None, None, width, height, None,
                             product.cache_identity, product.observation_id, product.wcs_status, reason)


def contains_sky_coordinate(product: NormalizedFitsProduct, ra_deg: float, dec_deg: float,
                            *, boundary_epsilon_px: float = BOUNDARY_EPSILON_PX) -> ContainmentResult:
    """Transform a celestial coordinate into the authoritative image-pixel domain."""
    try:
        raw_ra, raw_dec = float(ra_deg), float(dec_deg)
    except (TypeError, ValueError):
        return _unknown(product, ContainmentStatus.INVALID_COORDINATE, None, None, "RA/Dec must be numeric")
    if not (math.isfinite(raw_ra) and math.isfinite(raw_dec)) or not -90.0 <= raw_dec <= 90.0:
        return _unknown(product, ContainmentStatus.INVALID_COORDINATE, raw_ra, raw_dec, "RA/Dec is non-finite or Dec is outside [-90, 90]")
    ra = raw_ra % 360.0
    if product.wcs_status == WcsStatus.MISSING:
        return _unknown(product, ContainmentStatus.MISSING_WCS, ra, raw_dec, "No usable celestial WCS")
    if product.wcs_status != WcsStatus.VALID:
        return _unknown(product, ContainmentStatus.INVALID_WCS, ra, raw_dec, "Normalized product WCS is not VALID")
    if product.wcs is None:
        return _unknown(product, ContainmentStatus.MISSING_WCS, ra, raw_dec, "No usable celestial WCS object")
    if not product.image_shape or len(product.image_shape) != 2:
        return _unknown(product, ContainmentStatus.INVALID_WCS, ra, raw_dec, "Selected image has no two-dimensional shape")
    height, width = product.image_shape
    try:
        x, y = (float(value) for value in product.wcs.world_to_pixel_values(ra, raw_dec))
    except Exception as exc:
        return _unknown(product, ContainmentStatus.TRANSFORM_ERROR, ra, raw_dec, f"world-to-pixel failed: {exc}")
    if not (math.isfinite(x) and math.isfinite(y)):
        return _unknown(product, ContainmentStatus.TRANSFORM_ERROR, ra, raw_dec, "world-to-pixel returned non-finite coordinates")
    margins = (x + 0.5, width - 0.5 - x, y + 0.5, height - 0.5 - y)
    inside = all(margin >= -boundary_epsilon_px for margin in margins)
    distance = max(0.0, min(margins)) if inside else None
    if distance is not None and distance <= boundary_epsilon_px:
        distance = 0.0
    if not inside:
        status, boolean = ContainmentStatus.OUTSIDE, False
    elif distance is not None and distance <= boundary_epsilon_px:
        status, boolean = ContainmentStatus.BOUNDARY, True
    else:
        status, boolean = ContainmentStatus.INSIDE, True
    return ContainmentResult(status, boolean, ra, raw_dec, x, y, width, height, distance,
                             product.cache_identity, product.observation_id, product.wcs_status)


def observation_time_mjd(product: NormalizedFitsProduct) -> float | None:
    """Use archive bounds first, then FITS average/start timing if present."""
    if product.archive_timing_mjd:
        start, end = product.archive_timing_mjd
        if start is not None and end is not None:
            return (start + end) / 2.0
        if start is not None:
            return start
        if end is not None:
            return end
    for key in ("MJD-AVG", "MJD-OBS", "MJD-BEG"):
        value = product.fits_timing.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def match_ephemeris_to_product(product: NormalizedFitsProduct, ephemeris_rows: Iterable[Mapping[str, object]],
                               *, tolerance_seconds: float | None = None) -> list[EphemerisMatch]:
    """Apply spatial containment and independently classify timing for each row."""
    if tolerance_seconds is not None and tolerance_seconds < 0:
        raise ValueError("tolerance_seconds cannot be negative")
    product_time = observation_time_mjd(product)
    results = []
    for row in ephemeris_rows:
        def number(key: str) -> float | None:
            try:
                value = float(row[key])
                return value if math.isfinite(value) else None
            except (KeyError, TypeError, ValueError):
                return None
        mjd, ra, dec = number("mjd"), number("ra_deg"), number("dec_deg")
        containment = contains_sky_coordinate(product, float("nan") if ra is None else ra, float("nan") if dec is None else dec)
        offset = None if product_time is None or mjd is None else (mjd - product_time) * 86400.0
        if offset is None or tolerance_seconds is None:
            timing = TemporalStatus.UNKNOWN
        elif abs(offset) <= tolerance_seconds:
            timing = TemporalStatus.MATCH
        else:
            timing = TemporalStatus.OUTSIDE_TOLERANCE
        results.append(EphemerisMatch(None if row.get("object") is None else str(row.get("object")), mjd,
                                      containment, product_time, offset, timing))
    return results
