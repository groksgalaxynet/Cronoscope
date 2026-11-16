"""Pipeline 6: WCS registration, frozen Test-5 residual pairing, and contracts.

The detector below is a direct reusable adaptation of the frozen functions in
``py_files/atlas_test7_batch.py``.  Its default constants intentionally match
that evidence; this module does not optimize or retune them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any

import numpy as np
from reproject import reproject_interp
from scipy import ndimage

from .footprint import observation_time_mjd
from .models import NormalizedFitsProduct


class ComparisonStatus(str, Enum):
    SUCCESS = "SUCCESS"
    INVALID_PRODUCT = "INVALID_PRODUCT"
    INCOMPATIBLE_WCS = "INCOMPATIBLE_WCS"
    REGISTRATION_ERROR = "REGISTRATION_ERROR"
    NO_OVERLAP = "NO_OVERLAP"
    INSUFFICIENT_IMAGE_GEOMETRY = "INSUFFICIENT_IMAGE_GEOMETRY"
    INSUFFICIENT_OVERLAP = "INSUFFICIENT_OVERLAP"
    INVALID_DIFFERENCE = "INVALID_DIFFERENCE"


@dataclass(frozen=True)
class FrozenDetectorConfig:
    identity: str = "FROZEN_TEST5_TEST7_V1"
    threshold_sigma: float = 5.0
    border_pixels: int = 4
    minimum_component_area: int = 3
    connectivity: int = 8
    difference_direction: str = "registered_B_minus_A"
    pair_score_features: tuple[str, ...] = ("area", "flux", "peak", "width", "height")

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pair_score_features"] = list(self.pair_score_features)
        return payload


FROZEN_TEST5_TEST7_V1 = FrozenDetectorConfig()


@dataclass(frozen=True)
class ResidualBlob:
    label: int
    area: int
    x: float
    y: float
    flux: float
    peak: float
    width: int
    height: int

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MovingChangeCandidate:
    rank: int
    score: float
    separation_pixels: float
    negative: ResidualBlob
    positive: ResidualBlob
    similarities: dict[str, float]
    negative_sky_deg: tuple[float, float] | None
    positive_sky_deg: tuple[float, float] | None
    sky_warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "rank": self.rank, "score": self.score, "separation_pixels": self.separation_pixels,
            "negative": self.negative.to_jsonable(), "positive": self.positive.to_jsonable(),
            "similarities": self.similarities, "negative_sky_deg": self.negative_sky_deg,
            "positive_sky_deg": self.positive_sky_deg, "sky_warning": self.sky_warning,
        }


@dataclass(frozen=True)
class ComparisonResult:
    status: ComparisonStatus
    product_a_identity: str
    product_b_identity: str
    observation_a_id: str | None
    observation_b_id: str | None
    time_a_mjd: float | None
    time_b_mjd: float | None
    time_separation_seconds: float | None
    spectral_compatibility: str
    spatial_compatibility: str
    image_a_shape: tuple[int, ...] | None
    image_b_shape: tuple[int, ...] | None
    output_shape: tuple[int, ...] | None
    valid_pixel_count: int
    valid_pixel_fraction: float | None
    difference_statistics: dict[str, float | int | None]
    detector_config: FrozenDetectorConfig
    candidates: tuple[MovingChangeCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    candidate_analysis_status: str = "COMPLETE"
    # Display-only artifacts intentionally remain outside the JSON contract.
    # They are retained only by the in-process adapter after a successful run.
    science_image_a: Any = field(repr=False, compare=False, default=None)
    registered_image_b: Any = field(repr=False, compare=False, default=None)
    difference_image: Any = field(repr=False, compare=False, default=None)
    # Private, read-only context for display adapters.  It is deliberately not
    # part of the Pipeline 6 JSON contract or detector inputs.
    product_a: Any = field(repr=False, compare=False, default=None)
    product_b: Any = field(repr=False, compare=False, default=None)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "status": self.status.value, "product_a_identity": self.product_a_identity,
            "product_b_identity": self.product_b_identity, "observation_a_id": self.observation_a_id,
            "observation_b_id": self.observation_b_id, "time_a_mjd": self.time_a_mjd,
            "time_b_mjd": self.time_b_mjd, "time_separation_seconds": self.time_separation_seconds,
            "spectral_compatibility": self.spectral_compatibility, "spatial_compatibility": self.spatial_compatibility,
            "image_a_shape": None if self.image_a_shape is None else list(self.image_a_shape),
            "image_b_shape": None if self.image_b_shape is None else list(self.image_b_shape),
            "output_shape": None if self.output_shape is None else list(self.output_shape),
            "valid_pixel_count": self.valid_pixel_count, "valid_pixel_fraction": self.valid_pixel_fraction,
            "difference_statistics": self.difference_statistics, "detector_config": self.detector_config.to_jsonable(),
            "candidate_count": len(self.candidates), "candidates": [candidate.to_jsonable() for candidate in self.candidates],
            "warnings": list(self.warnings), "candidate_analysis_status": self.candidate_analysis_status,
        }


def spectral_compatibility(a: NormalizedFitsProduct, b: NormalizedFitsProduct) -> str:
    if a.archive_detector and b.archive_detector and a.archive_detector == b.archive_detector:
        return "SAME_ARCHIVE_CHANNEL"
    a_range, b_range = a.archive_wavelength_m, b.archive_wavelength_m
    if a_range and b_range and None not in (*a_range, *b_range):
        return "OVERLAPPING_WAVELENGTH" if max(a_range[0], b_range[0]) <= min(a_range[1], b_range[1]) else "DIFFERENT_WAVELENGTH"
    return "UNKNOWN"


def _ratio_similarity(a: float, b: float) -> float:
    a, b = abs(float(a)), abs(float(b))
    return 0.0 if a <= 0 or b <= 0 else min(a, b) / max(a, b)


def _measure_blobs(labels: np.ndarray, count: int, data: np.ndarray, median: float, positive: bool,
                   config: FrozenDetectorConfig) -> list[ResidualBlob]:
    blobs = []
    for label_id in range(1, count + 1):
        mask = labels == label_id
        area = int(np.count_nonzero(mask))
        if area < config.minimum_component_area:
            continue
        yy, xx = np.where(mask)
        weights = np.clip(data[mask] - median, 0, None) if positive else np.clip(median - data[mask], 0, None)
        total = float(np.sum(weights))
        if total <= 0:
            continue
        blobs.append(ResidualBlob(label_id, area, float(np.sum(xx * weights) / total), float(np.sum(yy * weights) / total),
                                  total, float(np.max(weights)), int(xx.max() - xx.min() + 1), int(yy.max() - yy.min() + 1)))
    return blobs


def _candidate(negative: ResidualBlob, positive: ResidualBlob) -> tuple[float, float, dict[str, float]]:
    similarities = {"area": _ratio_similarity(negative.area, positive.area), "flux": _ratio_similarity(negative.flux, positive.flux),
                    "peak": _ratio_similarity(negative.peak, positive.peak), "width": _ratio_similarity(negative.width, positive.width),
                    "height": _ratio_similarity(negative.height, positive.height)}
    return float(np.mean(list(similarities.values()))), float(np.hypot(positive.x - negative.x, positive.y - negative.y)), similarities


def _sky_coordinates(product: NormalizedFitsProduct, negative: ResidualBlob, positive: ResidualBlob) -> tuple[tuple[float, float] | None, tuple[float, float] | None, str | None]:
    try:
        neg = tuple(float(value) for value in product.wcs.pixel_to_world_values(negative.x, negative.y))
        pos = tuple(float(value) for value in product.wcs.pixel_to_world_values(positive.x, positive.y))
        return neg, pos, None
    except Exception as exc:
        return None, None, f"Candidate WCS conversion unavailable: {exc}"


def _empty(status: ComparisonStatus, a: NormalizedFitsProduct, b: NormalizedFitsProduct, *, warning: str,
           spatial: str = "UNKNOWN") -> ComparisonResult:
    ta, tb = observation_time_mjd(a), observation_time_mjd(b)
    separation = None if ta is None or tb is None else (tb - ta) * 86400.0
    return ComparisonResult(status, a.cache_identity, b.cache_identity, a.observation_id, b.observation_id, ta, tb, separation,
                            spectral_compatibility(a, b), spatial, a.image_shape, b.image_shape, None, 0, None, {},
                            FROZEN_TEST5_TEST7_V1, warnings=(warning,))


def compare_observations(product_a: NormalizedFitsProduct, product_b: NormalizedFitsProduct,
                         *, config: FrozenDetectorConfig = FROZEN_TEST5_TEST7_V1) -> ComparisonResult:
    """Register B to A, calculate ``registered_B - A``, then apply frozen pairing."""
    registration = register_observations(product_a, product_b, config=config)
    if registration.status is not ComparisonStatus.SUCCESS:
        return registration
    difference = np.asarray(registration.difference_image, dtype=float)
    valid_count = registration.valid_pixel_count
    stats = registration.difference_statistics
    sigma = stats["robust_sigma"]
    if sigma is None or not np.isfinite(sigma) or sigma <= 0:
        return replace(registration, status=ComparisonStatus.INVALID_DIFFERENCE, science_image_a=None,
                       registered_image_b=None, difference_image=None, product_a=None, product_b=None,
                       warnings=("Robust sigma is zero or invalid; frozen detector not applied.",))
    median = float(stats["median"])
    positive_mask = difference > median + config.threshold_sigma * sigma
    negative_mask = difference < median - config.threshold_sigma * sigma
    border = config.border_pixels
    for mask in (positive_mask, negative_mask):
        mask[:border, :] = mask[-border:, :] = False
        mask[:, :border] = mask[:, -border:] = False
    structure = np.ones((3, 3), dtype=int)
    positive_labels, positive_count = ndimage.label(positive_mask, structure=structure)
    negative_labels, negative_count = ndimage.label(negative_mask, structure=structure)
    positives = _measure_blobs(positive_labels, positive_count, difference, median, True, config)
    negatives = _measure_blobs(negative_labels, negative_count, difference, median, False, config)
    raw = []
    for negative in negatives:
        for positive in positives:
            score, distance, similarities = _candidate(negative, positive)
            raw.append((score, distance, similarities, negative, positive))
    raw.sort(key=lambda item: item[0], reverse=True)
    candidates = tuple(MovingChangeCandidate(rank, score, distance, negative, positive, similarities,
                                              *_sky_coordinates(product_a, negative, positive))
                       for rank, (score, distance, similarities, negative, positive) in enumerate(raw, 1))
    return replace(registration, candidates=candidates, warnings=(), candidate_analysis_status="COMPLETE")


def register_observations(product_a: NormalizedFitsProduct, product_b: NormalizedFitsProduct,
                          *, config: FrozenDetectorConfig = FROZEN_TEST5_TEST7_V1) -> ComparisonResult:
    """Create registered display artifacts without invoking the frozen detector.

    This is the safe visualization boundary: it retains the same validation,
    reprojection, and B-minus-A calculation as ``compare_observations`` but
    intentionally does not materialize residual candidate pairs.
    """
    if product_a.image is None or product_b.image is None or not product_a.image_shape or not product_b.image_shape:
        return _empty(ComparisonStatus.INVALID_PRODUCT, product_a, product_b, warning="Both products require a selected image array")
    if product_a.wcs is None or product_b.wcs is None or product_a.wcs_status.value != "VALID" or product_b.wcs_status.value != "VALID":
        return _empty(ComparisonStatus.INCOMPATIBLE_WCS, product_a, product_b, warning="Both products require VALID celestial WCS", spatial="INCOMPATIBLE")
    image_a, image_b = np.asarray(product_a.image, dtype=float), np.asarray(product_b.image, dtype=float)
    if image_a.ndim != 2 or image_b.ndim != 2:
        return _empty(ComparisonStatus.INVALID_PRODUCT, product_a, product_b,
                      warning="Both selected science arrays must be two-dimensional")
    # A one-sample axis is topologically one-dimensional even when FITS stores
    # it as a 2-D array.  IRSA can legitimately return this geometry when a
    # target-centred cutout clips a detector boundary; it must not be presented
    # as a usable sky image or stretched into one.
    if min(image_a.shape) < 2 or min(image_b.shape) < 2:
        return _empty(
            ComparisonStatus.INSUFFICIENT_IMAGE_GEOMETRY, product_a, product_b,
            warning=("A selected archive cutout has fewer than two samples on one spatial axis "
                     f"(A {image_a.shape[1]}x{image_a.shape[0]}, B {image_b.shape[1]}x{image_b.shape[0]} pixels); "
                     "choose another observation with genuine two-dimensional coverage."),
            spatial="INSUFFICIENT_GEOMETRY",
        )
    try:
        registered_b, footprint = reproject_interp((image_b, product_b.wcs), product_a.wcs, shape_out=image_a.shape)
    except Exception as exc:
        return _empty(ComparisonStatus.REGISTRATION_ERROR, product_a, product_b, warning=f"reproject_interp failed: {exc}", spatial="ERROR")
    valid = np.isfinite(image_a) & np.isfinite(registered_b) & (footprint > 0)
    valid_count = int(np.count_nonzero(valid))
    if valid_count == 0:
        return _empty(ComparisonStatus.NO_OVERLAP, product_a, product_b, warning="No finite registered overlap", spatial="NO_OVERLAP")
    valid_y, valid_x = np.nonzero(valid)
    overlap_height = int(valid_y.max() - valid_y.min() + 1)
    overlap_width = int(valid_x.max() - valid_x.min() + 1)
    if valid_count < 4 or overlap_height < 2 or overlap_width < 2:
        return _empty(
            ComparisonStatus.INSUFFICIENT_OVERLAP, product_a, product_b,
            warning=("Registered finite overlap is not genuinely two-dimensional "
                     f"({overlap_width}x{overlap_height} pixel bounds, {valid_count} valid pixels); "
                     "choose observations with broader shared sky coverage."),
            spatial="INSUFFICIENT_OVERLAP",
        )
    difference = registered_b - image_a  # Frozen Test-5/Test-7 direction.
    difference[~valid] = np.nan
    values = difference[np.isfinite(difference)]
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    sigma = float(1.4826 * mad)
    stats = {"finite_count": int(values.size), "min": float(np.min(values)), "max": float(np.max(values)), "mean": float(np.mean(values)),
             "median": median, "std": float(np.std(values)), "mad": mad, "robust_sigma": sigma}
    ta, tb = observation_time_mjd(product_a), observation_time_mjd(product_b)
    return ComparisonResult(ComparisonStatus.SUCCESS, product_a.cache_identity, product_b.cache_identity,
                            product_a.observation_id, product_b.observation_id, ta, tb,
                            None if ta is None or tb is None else (tb - ta) * 86400, spectral_compatibility(product_a, product_b),
                            "OVERLAP", image_a.shape, image_b.shape, image_a.shape, valid_count, valid_count / valid.size,
                            stats, config, warnings=("Candidate analysis was not run; registered display artifacts are ready.",),
                            candidate_analysis_status="NOT_RUN", science_image_a=image_a,
                            registered_image_b=registered_b, difference_image=difference,
                            product_a=product_a, product_b=product_b)
