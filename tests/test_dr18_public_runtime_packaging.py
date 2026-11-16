from __future__ import annotations

import json
from pathlib import Path

from web_app.api import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_moving_object_runtime_catalog_is_a_provenance_marked_subset() -> None:
    catalog = json.loads((ROOT / "web_app/data/moving_object_runtime_catalog.json").read_text())
    assert catalog["classification"] == "PUBLIC_RUNTIME_SUBSET_OF_VERIFIED_PHASE40D_EVIDENCE"
    assert catalog["derived_from"]["sha256"] == "7ef5606aaf37b49ed0fdec93193e75c7ad2920df7fcd86d5ba2adfc5f815ce6f"
    assert catalog["derived_from"]["method"] == "exact field selection; no scientific values recalculated"
    assert len(catalog["results"]) == 19
    assert create_app().moving_catalog.target_summaries()


def test_dr1_public_fixture_excludes_private_artifacts_and_records_source() -> None:
    fixture = json.loads((ROOT / "research/dr1_cube_service/fixtures/Npix7945_verified_samples.json").read_text())
    assert fixture["classification"] == "PUBLIC_REPLAY_OF_VERIFIED_DR1_RESULT"
    assert fixture["derived_from"]["sha256"] == "aa24f708a3d2d74443277769893230186fa8ba45a2943b3f4f3fecb4b26d57b1"
    assert fixture["derived_from"]["raw_range_responses_included"] is False
    assert len(fixture["samples"]) == 6
    assert not ({"ledger", "resource", "artifact_sha256"} & fixture.keys())
