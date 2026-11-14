"""Isolated, non-production paired weak-motion research primitives."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt

import numpy as np


@dataclass(frozen=True)
class V2ResearchConfig:
    identity: str = "V2_PAIRED_APERTURE_RESEARCH_V1"
    aperture_radius_px: int = 1
    background_inner_radius_px: int = 3
    background_outer_radius_px: int = 5
    control_count: int = 256
    control_seed: int = 20260921
    control_dx_px: int = -6
    control_dy_px: int = 0
    required_margin_px: int = 6

    def to_jsonable(self) -> dict: return asdict(self)


FROZEN_V2_PAIRED_APERTURE_RESEARCH_V1 = V2ResearchConfig()


def paired_statistic(old_evidence: float, new_evidence: float) -> float:
    """Combine expected negative/positive evidence, rejecting either wrong sign."""
    return 0.0 if old_evidence <= 0 or new_evidence <= 0 else (old_evidence + new_evidence) / sqrt(2.0)


def deterministic_control_paths(valid: np.ndarray, config: V2ResearchConfig = FROZEN_V2_PAIRED_APERTURE_RESEARCH_V1) -> list[tuple[int, int, int, int]]:
    """Return valid, non-target deterministic old/new pixel paths."""
    height, width = valid.shape; rng = np.random.default_rng(config.control_seed); paths = []
    attempts = 0
    while len(paths) < config.control_count and attempts < config.control_count * 100:
        attempts += 1; x = int(rng.integers(config.required_margin_px, width - config.required_margin_px)); y = int(rng.integers(config.required_margin_px, height - config.required_margin_px))
        bx, by = x + config.control_dx_px, y + config.control_dy_px
        if not (config.required_margin_px <= bx < width - config.required_margin_px and config.required_margin_px <= by < height - config.required_margin_px): continue
        if valid[y-config.required_margin_px:y+config.required_margin_px+1, x-config.required_margin_px:x+config.required_margin_px+1].all() and valid[by-config.required_margin_px:by+config.required_margin_px+1, bx-config.required_margin_px:bx+config.required_margin_px+1].all():
            paths.append((x, y, bx, by))
    if len(paths) != config.control_count: raise ValueError("insufficient valid pixels for frozen control population")
    return paths
