"""Pure Phase-19A population-selection helpers; no detector imports."""
from __future__ import annotations

import re
from typing import Iterable

ORIGINAL_EVALUATION_NUMBERS = frozenset({"6649", "31117", "163237", "179863"})
MAX_REPLICATION_TRACKS = 20


def asteroid_number(identifier: str) -> str | None:
    match = re.match(r"\s*(\d+)\b", identifier)
    return match.group(1) if match else None


def is_original_evaluation_object(identifier: str) -> bool:
    return asteroid_number(identifier) in ORIGINAL_EVALUATION_NUMBERS


def deterministic_track_order(identifiers: Iterable[str]) -> list[str]:
    """Sort independently of photometry, residuals, or detector outputs."""
    def key(identifier: str) -> tuple[int, int, str]:
        number = asteroid_number(identifier)
        return (0, int(number), identifier) if number is not None else (1, 0, identifier)
    return sorted(set(identifiers), key=key)
