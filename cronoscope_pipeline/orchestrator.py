"""Thin application-facing composition of Cronoscope Pipelines 1–6.

No FITS/WCS arrays or archive parser objects cross this boundary.  Product IDs
are opaque SHA-256-based selectors scoped to records held by an orchestrator.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from .comparison import FROZEN_TEST5_TEST7_V1, compare_observations, register_observations
from .discovery import (DEFAULT_COLLECTION, SUPPORTED_COLLECTIONS, DiscoveryError,
                        discover_observations, validate_collection)
from .fits_normalization import normalize_fits_product
from .grouping import group_observations
from .models import ObservationRecord
from .retrieval import retrieve_product

ORCHESTRATOR_VERSION = "PIPELINE7_V1"
PIPELINE_PROVENANCE = {
    "orchestrator": ORCHESTRATOR_VERSION,
    "discovery_normalization": "PIPELINE1_V1",
    "epoch_grouping": "PIPELINE2_V1",
    "retrieval_cache": "PIPELINE3_V1",
    "fits_normalization": "PIPELINE4_V1",
    "footprint_logic": "PIPELINE5_V1",
    "comparison": "PIPELINE6_V1",
    "frozen_detector": FROZEN_TEST5_TEST7_V1.identity,
}


def public_product_id(record: ObservationRecord) -> str:
    """Return an opaque, collision-resistant ID; never a cache filename/path."""
    material = "\x1f".join((record.raw_identifiers.get("obs_publisher_did", ""), record.observation_id or "",
                              record.band_label or "", repr(record.wavelength_min_m), repr(record.wavelength_max_m),
                              record.access_url or ""))
    return "spx_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _product_summary(record: ObservationRecord) -> dict[str, Any]:
    return {"product_id": public_product_id(record), "observation_id": record.observation_id, "time_start_mjd": record.t_min_mjd,
            "time_end_mjd": record.t_max_mjd, "detector": record.band_label,
            "wavelength_min_m": record.wavelength_min_m, "wavelength_max_m": record.wavelength_max_m,
            "collection": record.collection,
            "data_product_type": record.data_product_type, "access_format": record.access_format}


def release_compatibility(a: ObservationRecord, b: ObservationRecord) -> str | None:
    """Return a release-policy error before retrieval or scientific work."""
    if a.collection not in SUPPORTED_COLLECTIONS or b.collection not in SUPPORTED_COLLECTIONS:
        return "Comparison requires trusted QR2 or QR3 observation provenance."
    if a.collection != b.collection:
        return "QR2 and QR3 use different processing/calibration characteristics and cannot currently be compared in Cronoscope."
    return None


def _time_midpoint(record: ObservationRecord) -> float | None:
    if record.t_min_mjd is None:
        return record.t_max_mjd
    return record.t_min_mjd if record.t_max_mjd is None else (record.t_min_mjd + record.t_max_mjd) / 2.0


class CronoscopeOrchestrator:
    """Application-facing facade with injectable discovery/retrieval for replay."""

    def __init__(self, *, cache_dir: str = ".cronoscope_cache", discovery_fetcher: Callable[..., list[ObservationRecord]] = discover_observations,
                 retriever: Callable[..., Any] = retrieve_product, normalizer: Callable[..., Any] = normalize_fits_product,
                 comparator: Callable[..., Any] = compare_observations) -> None:
        self.cache_dir, self.discovery_fetcher, self.retriever = cache_dir, discovery_fetcher, retriever
        self.normalizer, self.comparator = normalizer, comparator
        self._records: dict[str, ObservationRecord] = {}
        self._comparison_artifacts: dict[str, Any] = {}

    def register_records(self, records: Iterable[ObservationRecord]) -> None:
        """Register saved/replay discovery records without changing their provenance."""
        for record in records:
            self._records[public_product_id(record)] = record

    def forget_records(self, product_ids: Iterable[str]) -> None:
        """Remove a bounded search result set from the in-memory registry."""
        for product_id in product_ids:
            self._records.pop(product_id, None)

    def comparison_artifact(self, comparison_id: str) -> Any | None:
        """Return a private display artifact; it is never serialized by Pipeline 7."""
        return self._comparison_artifacts.get(comparison_id)

    def search_sky(self, ra_deg: float, dec_deg: float, radius_deg: float, *, label: str | None = None,
                   collection: str = DEFAULT_COLLECTION) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            collection = validate_collection(collection)
            records = self.discovery_fetcher(ra_deg, dec_deg, radius_deg, label=label, collection=collection)
        except (DiscoveryError, ValueError) as exc:
            return self._envelope("search_sky", "DISCOVERY_ERROR", warnings=[], errors=[str(exc)], timings={"discovery_seconds": time.perf_counter() - started})
        discovery_seconds = time.perf_counter() - started
        grouping_started = time.perf_counter()
        self.register_records(records)
        group = group_observations(records, area_key=label or f"CIRCLE_{ra_deg}_{dec_deg}_{radius_deg}")
        epochs = [{"observation_id": epoch.observation_id, "start_mjd": epoch.start_mjd, "end_mjd": epoch.end_mjd,
                   "products": [_product_summary(record) for record in epoch.bands]} for epoch in group.epochs]
        labels = sorted({record.band_label for record in records if record.band_label})
        wavelengths = sorted({(record.wavelength_min_m, record.wavelength_max_m) for record in records}, key=lambda item: (float("inf") if item[0] is None else item[0], float("inf") if item[1] is None else item[1]))
        return self._envelope("search_sky", "SUCCESS", data={"query": {"ra_deg": ra_deg, "dec_deg": dec_deg, "radius_deg": radius_deg, "label": label, "collection": collection}, "collection": collection,
                              "product_count": len(records), "epoch_count": len(epochs), "detector_labels": labels,
                              "wavelength_ranges_m": [{"min": low, "max": high} for low, high in wavelengths], "epochs": epochs,
                              "products": [_product_summary(record) for record in records]}, warnings=list(group.warnings),
                              timings={"discovery_seconds": discovery_seconds, "grouping_seconds": time.perf_counter() - grouping_started,
                                       "total_seconds": time.perf_counter() - started})

    def list_comparison_options(self, product_ids: Iterable[str], *, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        if offset < 0 or limit <= 0:
            return self._envelope("list_comparison_options", "INVALID_REQUEST", errors=["offset must be >= 0 and limit must be positive"])
        unresolved = [item for item in product_ids if item not in self._records]
        if unresolved:
            return self._envelope("list_comparison_options", "INVALID_PRODUCT_ID", errors=[f"Unknown product ID: {unresolved[0]}"])
        records = sorted((self._records[item] for item in product_ids), key=lambda record: (_time_midpoint(record) is None, _time_midpoint(record), public_product_id(record)))
        if len(records) >= 2:
            error = release_compatibility(records[0], records[1])
            if error:
                return self._envelope("list_comparison_options", "CROSS_RELEASE_COMPARISON_BLOCKED", errors=[error])
        options = []
        for index, a in enumerate(records):
            for b in records[index + 1:]:
                if a.observation_id == b.observation_id:
                    continue
                if a.band_label and a.band_label == b.band_label:
                    category = "SAME_CHANNEL_TEMPORAL"
                elif a.wavelength_min_m is not None and a.wavelength_max_m is not None and b.wavelength_min_m is not None and b.wavelength_max_m is not None and max(a.wavelength_min_m, b.wavelength_min_m) <= min(a.wavelength_max_m, b.wavelength_max_m):
                    category = "OVERLAPPING_WAVELENGTH"
                else:
                    category = "CROSS_CHANNEL"
                ta, tb = _time_midpoint(a), _time_midpoint(b)
                options.append({"product_a_id": public_product_id(a), "product_b_id": public_product_id(b), "category": category,
                                "time_separation_seconds": None if ta is None or tb is None else abs(tb - ta) * 86400.0,
                                "product_a": _product_summary(a), "product_b": _product_summary(b)})
        category_order = {"SAME_CHANNEL_TEMPORAL": 0, "OVERLAPPING_WAVELENGTH": 1, "CROSS_CHANNEL": 2}
        options.sort(key=lambda item: (category_order[item["category"]], float("inf") if item["time_separation_seconds"] is None else item["time_separation_seconds"], item["product_a_id"], item["product_b_id"]))
        counts = Counter(item["category"] for item in options)
        return self._envelope("list_comparison_options", "SUCCESS", data={"total_options": len(options), "offset": offset, "limit": limit,
                              "category_counts": dict(counts), "options": options[offset:offset + limit]},
                              warnings=["Options are factual groupings, not a scientific ranking."])

    def compare_selected_products(self, product_a_id: str, product_b_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        a, b = self._records.get(product_a_id), self._records.get(product_b_id)
        if a is None or b is None:
            return self._envelope("compare_selected_products", "INVALID_PRODUCT_ID", errors=["One or both product IDs are unknown"])
        if error := release_compatibility(a, b):
            return self._envelope("compare_selected_products", "CROSS_RELEASE_COMPARISON_BLOCKED", errors=[error])
        retrieval_started = time.perf_counter()
        results = [self.retriever(record, self.cache_dir) for record in (a, b)]
        retrieval_seconds = time.perf_counter() - retrieval_started
        failed = next((result for result in results if not result.succeeded), None)
        if failed:
            return self._envelope("compare_selected_products", f"RETRIEVAL_{failed.status.value}", data={"retrieval": [result.to_jsonable() for result in results]},
                                  errors=[failed.message or "Product retrieval failed"], timings={"retrieval_seconds": retrieval_seconds, "total_seconds": time.perf_counter() - started})
        normalization_started = time.perf_counter()
        try:
            products = [self.normalizer(result, record) for result, record in zip(results, (a, b))]
        except Exception as exc:
            return self._envelope("compare_selected_products", "NORMALIZATION_ERROR", errors=[str(exc)],
                                  timings={"retrieval_seconds": retrieval_seconds, "normalization_seconds": time.perf_counter() - normalization_started,
                                           "total_seconds": time.perf_counter() - started})
        normalization_seconds = time.perf_counter() - normalization_started
        comparison_started = time.perf_counter()
        comparison = self.comparator(products[0], products[1])
        comparison_seconds = time.perf_counter() - comparison_started
        comparison_id = None
        if getattr(comparison, "science_image_a", None) is not None:
            comparison_id = "cmp_" + uuid.uuid4().hex
            self._comparison_artifacts[comparison_id] = comparison
        return self._envelope("compare_selected_products", comparison.status.value, data={"selection": {"product_a_id": product_a_id, "product_b_id": product_b_id},
                              "retrieval": [result.to_jsonable() for result in results],
                              "footprints": [{"wcs_status": product.wcs_status.value, "celestial_footprint_deg": product.celestial_footprint_deg} for product in products],
                              "comparison": comparison.to_jsonable(), "comparison_id": comparison_id}, warnings=list(comparison.warnings),
                              timings={"retrieval_seconds": retrieval_seconds, "normalization_seconds": normalization_seconds,
                                       "comparison_seconds": comparison_seconds, "total_seconds": time.perf_counter() - started})

    def prepare_selected_products(self, product_a_id: str, product_b_id: str) -> dict[str, Any]:
        """Prepare registered visual artifacts without running frozen candidate analysis."""
        started = time.perf_counter()
        a, b = self._records.get(product_a_id), self._records.get(product_b_id)
        if a is None or b is None:
            return self._envelope("prepare_selected_products", "INVALID_PRODUCT_ID", errors=["One or both product IDs are unknown"])
        if error := release_compatibility(a, b):
            return self._envelope("prepare_selected_products", "CROSS_RELEASE_COMPARISON_BLOCKED", errors=[error])
        retrieval_started = time.perf_counter()
        results = [self.retriever(record, self.cache_dir) for record in (a, b)]
        retrieval_seconds = time.perf_counter() - retrieval_started
        failed = next((result for result in results if not result.succeeded), None)
        if failed:
            return self._envelope("prepare_selected_products", f"RETRIEVAL_{failed.status.value}", data={"retrieval": [result.to_jsonable() for result in results]},
                                  errors=[failed.message or "Product retrieval failed"], timings={"retrieval_seconds": retrieval_seconds, "total_seconds": time.perf_counter() - started})
        normalization_started = time.perf_counter()
        try:
            products = [self.normalizer(result, record) for result, record in zip(results, (a, b))]
        except Exception as exc:
            return self._envelope("prepare_selected_products", "NORMALIZATION_ERROR", errors=[str(exc)],
                                  timings={"retrieval_seconds": retrieval_seconds, "normalization_seconds": time.perf_counter() - normalization_started,
                                           "total_seconds": time.perf_counter() - started})
        normalization_seconds = time.perf_counter() - normalization_started
        registration_started = time.perf_counter()
        comparison = register_observations(products[0], products[1])
        registration_seconds = time.perf_counter() - registration_started
        comparison_id = None
        if getattr(comparison, "science_image_a", None) is not None:
            comparison_id = "cmp_" + uuid.uuid4().hex
            self._comparison_artifacts[comparison_id] = comparison
        return self._envelope("prepare_selected_products", comparison.status.value, data={"selection": {"product_a_id": product_a_id, "product_b_id": product_b_id},
                              "retrieval": [result.to_jsonable() for result in results],
                              "footprints": [{"wcs_status": product.wcs_status.value, "celestial_footprint_deg": product.celestial_footprint_deg} for product in products],
                              "comparison": comparison.to_jsonable(), "comparison_id": comparison_id}, warnings=list(comparison.warnings),
                              timings={"retrieval_seconds": retrieval_seconds, "normalization_seconds": normalization_seconds,
                                       "registration_seconds": registration_seconds, "total_seconds": time.perf_counter() - started})

    @staticmethod
    def _envelope(operation: str, status: str, *, data: dict[str, Any] | None = None, warnings: list[str] | None = None,
                  errors: list[str] | None = None, timings: dict[str, float] | None = None) -> dict[str, Any]:
        return {"operation": operation, "status": status, "data": data or {}, "warnings": warnings or [], "errors": errors or [],
                "provenance": PIPELINE_PROVENANCE, "timings_seconds": timings or {}}
