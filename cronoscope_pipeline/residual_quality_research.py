"""Isolated target-blind residual-context research primitives; never production."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .coordinate_safe_evidence import CoordinateFrame, FramedPixel


@dataclass(frozen=True)
class ResidualQualityFeatures:
    """Continuous local context descriptors, not a detector decision."""
    valid: bool
    reason: str
    central_residual_concentration: float | None
    annulus_finite_fraction: float | None


@dataclass(frozen=True)
class PairRelativeQuality:
    """Descriptive pair-relative ranks; no threshold or categorical decision."""
    valid: bool
    reason: str
    central_concentration_percentile: float | None
    annulus_support_percentile: float | None


def residual_quality_features(difference: np.ndarray, coordinate: FramedPixel) -> ResidualQualityFeatures:
    """Reproduce Phase-36 21x21 concentration and frozen 3--5 annulus support."""
    if coordinate.frame != CoordinateFrame.A_REGISTERED_DIFFERENCE:
        return ResidualQualityFeatures(False, "FRAME_MISMATCH", None, None)
    if not (isfinite(coordinate.x) and isfinite(coordinate.y)):
        return ResidualQualityFeatures(False, "NONFINITE_COORDINATE", None, None)
    ix, iy = int(round(coordinate.x)), int(round(coordinate.y))
    if ix - 10 < 0 or iy - 10 < 0 or ix + 10 >= difference.shape[1] or iy + 10 >= difference.shape[0]:
        return ResidualQualityFeatures(False, "WINDOW_OUT_OF_BOUNDS", None, None)
    window = difference[iy - 10:iy + 11, ix - 10:ix + 11]
    finite = np.isfinite(window)
    yy, xx = np.indices(window.shape)
    distance = np.maximum(abs(xx - 10), abs(yy - 10))
    central_finite = finite[distance <= 1]
    if not central_finite.all():
        return ResidualQualityFeatures(False, "INVALID_CENTRAL_SUPPORT", None, None)
    values = window[finite]
    if not len(values):
        return ResidualQualityFeatures(False, "NO_FINITE_WINDOW", None, None)
    median = float(np.median(values))
    centered = np.where(finite, window - median, 0.0)
    denominator = float(np.abs(centered).sum())
    if not isfinite(denominator) or denominator == 0:
        return ResidualQualityFeatures(False, "DEGENERATE_ZERO_RESIDUAL_ENERGY", None, None)
    concentration = float(np.abs(centered[distance <= 1]).sum() / denominator)
    annulus = finite[(distance >= 3) & (distance <= 5)]
    return ResidualQualityFeatures(True, "", concentration, float(annulus.mean()))


def pair_relative_quality(features: ResidualQualityFeatures, reference: list[ResidualQualityFeatures]) -> PairRelativeQuality:
    """Inclusive ranks against one deterministic matching-pair reference population."""
    if not features.valid:
        return PairRelativeQuality(False, features.reason, None, None)
    valid = [item for item in reference if item.valid]
    if not valid:
        return PairRelativeQuality(False, "NO_VALID_PAIR_REFERENCE", None, None)
    concentration = [item.central_residual_concentration for item in valid]
    annulus = [item.annulus_finite_fraction for item in valid]
    if any(value is None for value in concentration + annulus):
        return PairRelativeQuality(False, "INVALID_PAIR_REFERENCE", None, None)
    return PairRelativeQuality(
        True,
        "",
        100.0 * sum(value <= features.central_residual_concentration for value in concentration) / len(concentration),
        100.0 * sum(value <= features.annulus_finite_fraction for value in annulus) / len(annulus),
    )
