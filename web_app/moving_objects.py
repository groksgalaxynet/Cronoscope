"""Read-only target/observation view models for the Moving Object Explorer.

The contracts deliberately describe a target and observations rather than an
asteroid-only UI.  The first catalog source is frozen moving-object evidence;
stationary targets can supply fixed sky positions through the same contract.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cronoscope_pipeline.models import ObservationRecord

ROOT = Path(__file__).resolve().parents[1]
FROZEN_EVIDENCE = ROOT / "tests/test40d_frozen_population_detector_evaluation" / "frozen_population_detector_evidence.json"
FROZEN_POPULATION = ROOT / "tests/test40b_balanced_multipair_population" / "balanced_multipair_population.json"
INVENTORY = ROOT / "csv" / "test9_stage1b_observations.csv"


def _observation(row: dict[str, str]) -> ObservationRecord:
    return ObservationRecord(row["obs_id"], float(row["s_ra"]), float(row["s_dec"]), float(row["t_min"]), float(row["t_max"]),
                             float(row["em_min"]), float(row["em_max"]), row["energy_bandpassname"], int(row["calib_level"]),
                             row["dataproduct_type"], row["access_url"], row["access_format"], None, row["obs_collection"],
                             row["instrument_name"], row["target_name"], None, None, {"obs_publisher_did": row["obs_publisher_did"]})


@dataclass(frozen=True)
class MovingObjectCatalog:
    """Frozen moving-object records plus reusable archive observation metadata."""

    tracks: dict[str, dict[str, Any]]
    archive_rows: dict[str, ObservationRecord]

    @classmethod
    def from_frozen_artifacts(cls, evidence_path: Path = FROZEN_EVIDENCE, inventory_path: Path = INVENTORY,
                              population_path: Path = FROZEN_POPULATION) -> "MovingObjectCatalog":
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        positions = {str(item["asteroid_number"]): item for item in json.loads(population_path.read_text(encoding="utf-8"))["accepted_tracks"]}
        tracks = {str(item["asteroid_number"]): {**positions[str(item["asteroid_number"])], **item} for item in evidence["results"]}
        with inventory_path.open(newline="", encoding="utf-8") as handle:
            archive_rows = {row["obs_id"]: _observation(row) for row in csv.DictReader(handle)
                            if row["dataproduct_type"] == "image" and row["calib_level"] == "2"
                            and row["energy_bandpassname"] == "SPHEREx-D3"}
        return cls(tracks, archive_rows)

    def target_summaries(self) -> list[dict[str, Any]]:
        items = []
        for asteroid_id in sorted(self.tracks, key=lambda value: int(value)):
            track = self.tracks[asteroid_id]
            items.append({"target": {"id": asteroid_id, "label": track["asteroid_identifier"], "type": "moving_object"},
                          "observation_count": 2, "time_span_seconds": track["geometry"]["epoch_separation_seconds"],
                          "field_id": track["field_id"], "band_labels": self._band_labels(track),
                          "detail_endpoint": f"/api/moving-objects/{asteroid_id}"})
        return items

    def _band_labels(self, track: dict[str, Any]) -> list[str]:
        labels = []
        for obs_id in (track["product_a_obs_id"], track["product_b_obs_id"]):
            product = self.archive_rows.get(obs_id)
            if product and product.band_label not in labels:
                labels.append(product.band_label)
        return labels

    def detail(self, asteroid_id: str) -> dict[str, Any] | None:
        track = self.tracks.get(str(asteroid_id))
        if track is None:
            return None
        records = (("old", "product_a_obs_id", "epoch_a_utc", "ra_a_deg", "dec_a_deg"),
                   ("new", "product_b_obs_id", "epoch_b_utc", "ra_b_deg", "dec_b_deg"))
        observations = []
        for index, (role, product_key, epoch_key, ra_key, dec_key) in enumerate(records):
            product = self.archive_rows.get(track[product_key])
            observations.append({"role": role, "observation_id": track[product_key], "epoch_utc": track[epoch_key],
                                 "sky_position": {"ra_deg": track[ra_key], "dec_deg": track[dec_key], "coordinate_type": "Horizons predicted"},
                                 "wavelength": {"band_label": product.band_label if product else None,
                                                "minimum_m": product.wavelength_min_m if product else None,
                                                "maximum_m": product.wavelength_max_m if product else None},
                                 "image": {"cutout_endpoint": f"/api/moving-objects/{asteroid_id}/image/{role}", "available": product is not None},
                                 "relationship": {"previous": None if index == 0 else track["product_a_obs_id"],
                                                  "next": track["product_b_obs_id"] if index == 0 else None},
                                 "provenance": {"source": "SPHEREx/IRSA Level-2 observation inventory", "observation_id": track[product_key]}})
        if track["base_valid"]:
            v2 = {"status": "AVAILABLE", "label": "Experimental image evidence — not a detection",
                  "percentile": track["v2_control_percentile"], "signed_old_measurement": track["e_old"],
                  "signed_new_measurement": track["e_new"], "both_sign_result": track["both_sign_gate"],
                  "control_count": 256, "provenance": "Frozen Cronoscope Phase-40D V2 evidence"}
        else:
            v2 = {"status": "INVALID", "label": "Experimental image evidence — not a detection",
                  "reason": track.get("base_reason"), "percentile": None, "signed_old_measurement": None,
                  "signed_new_measurement": None, "both_sign_result": None, "control_count": 256,
                  "provenance": "Frozen Cronoscope Phase-40D V2 evidence"}
        return {"target": {"id": str(asteroid_id), "label": track["asteroid_identifier"], "type": "moving_object"},
                "observations": observations, "motion": {"elapsed_seconds": track["geometry"]["epoch_separation_seconds"],
                           "angular_displacement_deg": track["geometry"]["angular_displacement_deg"],
                           "apparent_angular_rate_deg_per_day": track["geometry"]["apparent_angular_rate_deg_per_day"],
                           "coordinate_provenance": "JPL Horizons predictions frozen with the Phase-40B population"},
                "v2_evidence": v2,
                "provenance": {"spherex": "SPHEREx/IRSA Level-2", "horizons": "JPL Horizons", "evidence": "Frozen Cronoscope Phase-40D"}}

    def observation_for_image(self, asteroid_id: str, role: str) -> tuple[ObservationRecord, dict[str, Any]] | None:
        detail = self.detail(asteroid_id)
        if detail is None or role not in {"old", "new"}:
            return None
        observation = next(item for item in detail["observations"] if item["role"] == role)
        product = self.archive_rows.get(observation["observation_id"])
        return (product, observation) if product else None
