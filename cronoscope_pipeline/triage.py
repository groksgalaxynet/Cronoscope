"""Non-authoritative presentation helpers for immutable Pipeline 6 candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable

from .comparison import MovingChangeCandidate


class ValidationStatus(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    NO_MATCH = "NO_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    MATCH_WITHIN_CONFIGURED_TOLERANCE = "MATCH_WITHIN_CONFIGURED_TOLERANCE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class KnownObjectAnnotation:
    """Separate provenance, never an input to candidate generation or score."""
    status: ValidationStatus
    object_identity: str | None = None
    ephemeris_source: str | None = None
    observer_geometry: str | None = None
    ephemeris_epoch_mjd: float | None = None
    predicted_ra_deg: float | None = None
    predicted_dec_deg: float | None = None
    candidate_ra_deg: float | None = None
    candidate_dec_deg: float | None = None
    angular_separation_arcsec: float | None = None
    time_offset_seconds: float | None = None
    spatial_tolerance_pixels: float | None = None
    temporal_tolerance_seconds: float | None = None
    warnings: tuple[str, ...] = ()
    provenance: str = "No known-object validation has been requested."

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self); payload["status"] = self.status.value; payload["warnings"] = list(self.warnings)
        return payload


def presentation(candidate: MovingChangeCandidate, annotation: KnownObjectAnnotation | None = None) -> dict[str, Any]:
    """Copy factual detector values without changing the candidate or its score."""
    return {"candidate_id": f"cand_{candidate.rank:03d}", "detector_rank": candidate.rank,
            "detector_score": candidate.score, "separation_pixels": candidate.separation_pixels,
            "positive": candidate.positive.to_jsonable(), "negative": candidate.negative.to_jsonable(),
            "positive_sky_deg": candidate.positive_sky_deg, "negative_sky_deg": candidate.negative_sky_deg,
            "validation": (annotation or KnownObjectAnnotation(ValidationStatus.NOT_CHECKED)).to_jsonable()}


def sort_presentations(rows: Iterable[dict[str, Any]], field: str = "detector_score", descending: bool = True) -> list[dict[str, Any]]:
    allowed = {"detector_rank", "detector_score", "separation_pixels", "positive_flux", "negative_flux", "component_area"}
    if field not in allowed:
        raise ValueError(f"Unsupported presentation sort: {field}")
    def key(row: dict[str, Any]) -> tuple[float, int]:
        if field == "positive_flux": value = row["positive"]["flux"]
        elif field == "negative_flux": value = row["negative"]["flux"]
        elif field == "component_area": value = max(row["positive"]["area"], row["negative"]["area"])
        else: value = row[field]
        return float(value), int(row["detector_rank"])
    return sorted(rows, key=key, reverse=descending)


def filter_presentations(rows: Iterable[dict[str, Any],], *, min_score: float | None = None,
                         min_separation: float | None = None, max_separation: float | None = None,
                         min_area: int | None = None, require_sky: bool = False) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if min_score is not None and row["detector_score"] < min_score: continue
        if min_separation is not None and row["separation_pixels"] < min_separation: continue
        if max_separation is not None and row["separation_pixels"] > max_separation: continue
        if min_area is not None and max(row["positive"]["area"], row["negative"]["area"]) < min_area: continue
        if require_sky and (row["positive_sky_deg"] is None or row["negative_sky_deg"] is None): continue
        result.append(row)
    return result


def controlled_test7_annotation(candidate: MovingChangeCandidate) -> KnownObjectAnnotation:
    """Saved case-1 association only; this is not a live ephemeris query."""
    if candidate.rank != 41:
        return KnownObjectAnnotation(ValidationStatus.NOT_CHECKED)
    return KnownObjectAnnotation(
        ValidationStatus.MATCH_WITHIN_CONFIGURED_TOLERANCE, object_identity="3I/ATLAS (saved Test 7 validation target)",
        ephemeris_source="Saved Test 7 frozen validation evidence", observer_geometry="EARTH_GEOCENTRIC",
        predicted_ra_deg=248.79001446341786, predicted_dec_deg=-17.051271736672074,
        candidate_ra_deg=candidate.negative_sky_deg[0] if candidate.negative_sky_deg else None,
        candidate_dec_deg=candidate.negative_sky_deg[1] if candidate.negative_sky_deg else None,
        spatial_tolerance_pixels=5.0, temporal_tolerance_seconds=None,
        warnings=("Historical validation association only; detector score and rank were not changed.",
                  "EARTH_GEOCENTRIC provenance is not exact SPHEREx-observer geometry; spacecraft parallax is not modeled."),
        provenance="Saved Test 7 case 1 recorded candidate rank 41 with 0.155 px/0.263 px truth-position errors.")
