#!/usr/bin/env python3
"""Derive the public runtime subset of the frozen Phase-40D evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path


POSITION_FIELDS = (
    "asteroid_identifier", "asteroid_number", "field_id", "product_a_obs_id",
    "product_b_obs_id", "epoch_a_utc", "epoch_b_utc", "ra_a_deg", "dec_a_deg",
    "ra_b_deg", "dec_b_deg",
)
EVIDENCE_FIELDS = (
    "asteroid_identifier", "asteroid_number", "field_id", "product_a_obs_id",
    "product_b_obs_id", "epoch_a_utc", "epoch_b_utc", "base_valid",
    "base_reason", "e_old", "e_new", "both_sign_gate", "v2_control_percentile",
    "geometry",
)
OBSERVATION_FIELDS = (
    "obs_id", "s_ra", "s_dec", "t_min", "t_max", "em_min", "em_max",
    "energy_bandpassname", "calib_level", "dataproduct_type", "access_url",
    "access_format", "obs_collection", "instrument_name", "target_name",
    "obs_publisher_did",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("population", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    evidence_raw = args.evidence.read_bytes()
    population_raw = args.population.read_bytes()
    inventory_raw = args.inventory.read_bytes()
    evidence = json.loads(evidence_raw)
    population = json.loads(population_raw)
    positions = {
        str(item["asteroid_number"]): {field: item[field] for field in POSITION_FIELDS}
        for item in population["accepted_tracks"]
    }
    results = [
        {
            **positions[str(item["asteroid_number"])],
            **{field: item.get(field) for field in EVIDENCE_FIELDS},
        }
        for item in evidence["results"]
    ]
    observation_ids = {
        result[key] for result in results
        for key in ("product_a_obs_id", "product_b_obs_id")
    }
    inventory_rows = csv.DictReader(io.StringIO(inventory_raw.decode("utf-8")))
    archive_rows = [
        {field: row[field] for field in OBSERVATION_FIELDS}
        for row in inventory_rows
        if row["obs_id"] in observation_ids and row["dataproduct_type"] == "image"
        and row["calib_level"] == "2" and row["energy_bandpassname"] == "SPHEREx-D3"
    ]
    derived = {
        "schema_version": 1,
        "classification": "PUBLIC_RUNTIME_CATALOG_DERIVED_FROM_VERIFIED_PHASE40B_40D",
        "derived_from": {
            "phase40d_evidence": {
                "artifact": "frozen_population_detector_evidence.json",
                "sha256": hashlib.sha256(evidence_raw).hexdigest(),
            },
            "phase40b_population": {
                "artifact": "balanced_multipair_population.json",
                "sha256": hashlib.sha256(population_raw).hexdigest(),
            },
            "stage1b_inventory": {
                "artifact": "test9_stage1b_observations.csv",
                "sha256": hashlib.sha256(inventory_raw).hexdigest(),
            },
            "method": "exact runtime field selection and asteroid-number key merge; no scientific values recalculated",
        },
        "results": results,
        "archive_rows": archive_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
