#!/usr/bin/env python3
"""Derive a public-safe result replay from the verified DR1.5 result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SAMPLE_FIELDS = ("request", "arrays", "ranges", "science", "coordinates", "provenance", "validation", "limitations")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    source = json.loads(raw)
    derived = {
        "schema_version": 1,
        "classification": "PUBLIC_REPLAY_OF_VERIFIED_DR1_RESULT",
        "derived_from": {
            "experiment_id": source["experiment_id"],
            "artifact": "multi_channel_result.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "method": "exact field selection; no pixel or metadata values recalculated",
            "raw_range_responses_included": False,
        },
        "product_identity": source["product_identity"],
        "channels": source["channels"],
        "regions": source["regions"],
        "samples": [
            {field: sample[field] for field in SAMPLE_FIELDS}
            for sample in source["samples"]
        ],
        "limitations": source["limitations"] + [
            "This public artifact replays an already verified result; it does not independently decode the FITS product."
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
