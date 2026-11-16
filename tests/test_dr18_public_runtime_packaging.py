from __future__ import annotations

import json
from pathlib import Path

import web_app.api as web_api
from web_app.api import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_moving_object_runtime_catalog_is_a_provenance_marked_subset(tmp_path, monkeypatch) -> None:
    catalog = json.loads((ROOT / "web_app/data/moving_object_runtime_catalog.json").read_text())
    assert catalog["classification"] == "PUBLIC_RUNTIME_CATALOG_DERIVED_FROM_VERIFIED_PHASE40B_40D"
    assert catalog["derived_from"]["phase40d_evidence"]["sha256"] == "7ef5606aaf37b49ed0fdec93193e75c7ad2920df7fcd86d5ba2adfc5f815ce6f"
    assert catalog["derived_from"]["phase40b_population"]["sha256"] == "b8c48f7e8018b3c738bf03474badb8c6915f9d97870915f3184f232fb2406a77"
    assert catalog["derived_from"]["stage1b_inventory"]["sha256"] == "f1e38089f29093b10cee61866cd22e9c1825abcfedd80db225cd024513764921"
    assert "no scientific values recalculated" in catalog["derived_from"]["method"]
    assert len(catalog["results"]) == 19
    assert len(catalog["archive_rows"]) == 10
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    app = create_app()
    assert app.moving_catalog.target_summaries()
    search = app.replay.search_sky(30, 0, 0.1, collection="spherex_qr2")
    product_ids = [item["product_id"] for item in search["data"]["products"]]
    unavailable = app.replay.compare_selected_products(*product_ids)
    assert unavailable["status"] == "RETRIEVAL_INVALID_CONTENT"
    assert "no value was fabricated" in unavailable["errors"][0]


def test_dr1_public_fixture_excludes_private_artifacts_and_records_source() -> None:
    fixture = json.loads((ROOT / "research/dr1_cube_service/fixtures/Npix7945_verified_samples.json").read_text())
    assert fixture["classification"] == "PUBLIC_REPLAY_OF_VERIFIED_DR1_RESULT"
    assert fixture["derived_from"]["sha256"] == "aa24f708a3d2d74443277769893230186fa8ba45a2943b3f4f3fecb4b26d57b1"
    assert fixture["derived_from"]["raw_range_responses_included"] is False
    assert len(fixture["samples"]) == 6
    assert not ({"ledger", "resource", "artifact_sha256"} & fixture.keys())
