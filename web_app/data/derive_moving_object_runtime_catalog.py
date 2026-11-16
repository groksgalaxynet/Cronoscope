#!/usr/bin/env python3
"""Derive the public runtime subset of the frozen Phase-40D evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


USED_RESULT_FIELDS = (
    "asteroid_identifier", "asteroid_number", "field_id", "product_a_obs_id",
    "product_b_obs_id", "epoch_a_utc", "epoch_b_utc", "base_valid",
    "base_reason", "e_old", "e_new", "both_sign_gate", "v2_control_percentile",
    "geometry",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    source = json.loads(raw)
    derived = {
        "schema_version": 1,
        "classification": "PUBLIC_RUNTIME_SUBSET_OF_VERIFIED_PHASE40D_EVIDENCE",
        "derived_from": {
            "artifact": "frozen_population_detector_evidence.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "method": "exact field selection; no scientific values recalculated",
        },
        "results": [
            {field: item.get(field) for field in USED_RESULT_FIELDS}
            for item in source["results"]
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
