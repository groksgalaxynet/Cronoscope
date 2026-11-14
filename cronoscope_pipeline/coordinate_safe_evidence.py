"""Isolated, frame-safe paired-evidence research seam; never production."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, nan, radians, sqrt
from typing import Any

import numpy as np


class CoordinateFrame(str, Enum):
    A_NATIVE = "A_NATIVE"
    B_NATIVE = "B_NATIVE"
    A_REGISTERED_DIFFERENCE = "A_REGISTERED_DIFFERENCE"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    FRAME_MISMATCH = "FRAME_MISMATCH"
    APERTURE_OUT_OF_BOUNDS = "APERTURE_OUT_OF_BOUNDS"
    INSUFFICIENT_FINITE_APERTURE = "INSUFFICIENT_FINITE_APERTURE"
    INVALID_BACKGROUND_OR_NOISE = "INVALID_BACKGROUND_OR_NOISE"
    WCS_TRANSFORM_FAILURE = "WCS_TRANSFORM_FAILURE"


@dataclass(frozen=True)
class SkyPosition:
    ra_deg: float
    dec_deg: float


@dataclass(frozen=True)
class FramedPixel:
    x: float
    y: float
    frame: CoordinateFrame


@dataclass(frozen=True)
class PairedCoordinates:
    old_a_native: FramedPixel
    new_b_native: FramedPixel
    old_a_registered: FramedPixel
    new_a_registered: FramedPixel
    angular_motion_deg: float
    registered_dx_px: float
    registered_dy_px: float


@dataclass(frozen=True)
class EvidenceSample:
    status: EvidenceStatus
    reason: str
    coordinate: FramedPixel
    evidence: float | None = None
    background: float | None = None
    noise: float | None = None


def project_sky(wcs: Any, sky: SkyPosition, frame: CoordinateFrame) -> FramedPixel:
    try:
        x, y = (float(value) for value in wcs.world_to_pixel_values(sky.ra_deg, sky.dec_deg))
    except Exception as exc:
        raise ValueError(f"WCS transformation failure: {exc}") from exc
    if not (isfinite(x) and isfinite(y)):
        raise ValueError("WCS transformation returned non-finite pixel coordinates")
    return FramedPixel(x, y, frame)


def project_sky_safe(wcs: Any, sky: SkyPosition, frame: CoordinateFrame) -> FramedPixel | EvidenceSample:
    """Represent a WCS failure explicitly instead of manufacturing evidence."""
    try:
        return project_sky(wcs, sky, frame)
    except ValueError as exc:
        return EvidenceSample(
            EvidenceStatus.WCS_TRANSFORM_FAILURE,
            str(exc),
            FramedPixel(nan, nan, frame),
        )


def coordinate_contract(a_wcs: Any, b_wcs: Any, old_sky: SkyPosition, new_sky: SkyPosition) -> PairedCoordinates:
    old_a = project_sky(a_wcs, old_sky, CoordinateFrame.A_NATIVE)
    new_b = project_sky(b_wcs, new_sky, CoordinateFrame.B_NATIVE)
    old_registered = FramedPixel(old_a.x, old_a.y, CoordinateFrame.A_REGISTERED_DIFFERENCE)
    new_registered = project_sky(a_wcs, new_sky, CoordinateFrame.A_REGISTERED_DIFFERENCE)
    dra = ((new_sky.ra_deg - old_sky.ra_deg + 180.0) % 360.0) - 180.0
    angular = sqrt((dra * cos(radians((old_sky.dec_deg + new_sky.dec_deg) / 2.0))) ** 2 + (new_sky.dec_deg - old_sky.dec_deg) ** 2)
    return PairedCoordinates(old_a, new_b, old_registered, new_registered, angular, new_registered.x - old_registered.x, new_registered.y - old_registered.y)


def sample_difference_evidence(difference: np.ndarray, variance: np.ndarray, sampled_frame: CoordinateFrame, coordinate: FramedPixel, expected_sign: int) -> EvidenceSample:
    if sampled_frame != CoordinateFrame.A_REGISTERED_DIFFERENCE or coordinate.frame != sampled_frame:
        return EvidenceSample(EvidenceStatus.FRAME_MISMATCH, f"cannot sample {sampled_frame.value} with {coordinate.frame.value}", coordinate)
    if expected_sign not in (-1, 1):
        return EvidenceSample(EvidenceStatus.INVALID_BACKGROUND_OR_NOISE, "expected sign must be -1 or +1", coordinate)
    ix, iy = int(round(coordinate.x)), int(round(coordinate.y)); outer = 5
    if ix - outer < 0 or iy - outer < 0 or ix + outer >= difference.shape[1] or iy + outer >= difference.shape[0]:
        return EvidenceSample(EvidenceStatus.APERTURE_OUT_OF_BOUNDS, "5-pixel local support is outside A-grid difference image", coordinate)
    yy, xx = np.ogrid[iy-outer:iy+outer+1, ix-outer:ix+outer+1]; distance = np.maximum(abs(xx-ix), abs(yy-iy)); cut=difference[iy-outer:iy+outer+1,ix-outer:ix+outer+1]; vcut=variance[iy-outer:iy+outer+1,ix-outer:ix+outer+1]
    signal=cut[distance<=1]; background=cut[(distance>=3)&(distance<=5)]; signal_var=vcut[distance<=1]
    expected_aperture_samples = signal.size
    signal=signal[np.isfinite(signal)]; background=background[np.isfinite(background)]; signal_var=signal_var[np.isfinite(signal_var)]
    if len(signal) != expected_aperture_samples:
        return EvidenceSample(EvidenceStatus.INSUFFICIENT_FINITE_APERTURE, "3x3 A-grid aperture is not fully finite", coordinate)
    if not len(background) or not len(signal_var): return EvidenceSample(EvidenceStatus.INVALID_BACKGROUND_OR_NOISE, "background or variance support is non-finite", coordinate)
    bg=float(np.median(background)); mad=float(np.median(abs(background-bg))); noise=max(1.4826*mad,float(np.sqrt(np.median(signal_var))))
    if not isfinite(noise) or noise <= 0: return EvidenceSample(EvidenceStatus.INVALID_BACKGROUND_OR_NOISE, "local noise is non-finite or non-positive", coordinate, background=bg, noise=noise)
    evidence=expected_sign*(float(np.mean(signal))-bg)/(noise/sqrt(len(signal)))
    return EvidenceSample(EvidenceStatus.VALID, "", coordinate, evidence, bg, noise)
