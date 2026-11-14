"""Frozen Phase-23 V3 research primitive; never a production detector."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, sqrt

@dataclass(frozen=True)
class V3Diagnostic:
    e_old: float
    e_new: float
    old_background: float | None = None
    new_background: float | None = None
    old_noise: float | None = None
    new_noise: float | None = None

    @property
    def valid(self) -> bool:
        return isfinite(self.e_old) and isfinite(self.e_new)

    @property
    def statistic(self) -> float | None:
        return (self.e_old + self.e_new) / sqrt(2.0) if self.valid else None

def paired_statistic_v3(e_old: float, e_new: float) -> float | None:
    """S3=(e_old+e_new)/sqrt(2); invalid values are never coerced to zero."""
    return V3Diagnostic(e_old, e_new).statistic

def inclusive_percentile(control_scores: list[float], target_score: float) -> float | None:
    """Frozen inclusive rank; invalid inputs return invalid rather than a rank."""
    if not control_scores or not isfinite(target_score) or not all(isfinite(x) for x in control_scores):
        return None
    return 100.0 * sum(x <= target_score for x in control_scores) / len(control_scores)
