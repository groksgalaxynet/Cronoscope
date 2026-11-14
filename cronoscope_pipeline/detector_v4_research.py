"""Frozen Phase-27 V4 research primitive; never a production detector."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt, tanh


@dataclass(frozen=True)
class V4Diagnostic:
    """Signed V4 evidence and retained local diagnostic context."""
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
    def transformed_old(self) -> float | None:
        return tanh(self.e_old) if self.valid else None

    @property
    def transformed_new(self) -> float | None:
        return tanh(self.e_new) if self.valid else None

    @property
    def statistic(self) -> float | None:
        if not self.valid:
            return None
        return (self.transformed_old + self.transformed_new) / sqrt(2.0)


def paired_statistic_v4(e_old: float, e_new: float) -> float | None:
    """S4=(tanh(e_old)+tanh(e_new))/sqrt(2), with no tunable scale."""
    return V4Diagnostic(e_old, e_new).statistic


def inclusive_percentile(control_scores: list[float], target_score: float) -> float | None:
    """Frozen inclusive rank; invalid values are never assigned a rank."""
    if not control_scores or not isfinite(target_score) or not all(isfinite(score) for score in control_scores):
        return None
    return 100.0 * sum(score <= target_score for score in control_scores) / len(control_scores)
