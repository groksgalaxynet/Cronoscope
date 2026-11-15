"""Small stdlib WSGI adapter; scientific processing remains in Pipeline 1–7."""

from __future__ import annotations

import io
import json
import re
import threading
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import numpy as np
from astropy.io import fits
from PIL import Image, ImageDraw

from cronoscope_pipeline.comparison import FROZEN_TEST5_TEST7_V1
from cronoscope_pipeline.discovery import DEFAULT_COLLECTION, SUPPORTED_COLLECTIONS, supported_collections_text
from cronoscope_pipeline.fits_normalization import normalize_fits_product
from cronoscope_pipeline.models import FitsValidation, ObservationRecord, RetrievalResult, RetrievalStatus
from cronoscope_pipeline.orchestrator import ORCHESTRATOR_VERSION, CronoscopeOrchestrator
from cronoscope_pipeline.retrieval import retrieve_product
from cronoscope_pipeline.footprint import contains_sky_coordinate
from cronoscope_pipeline.science_interface import (highlight_wavelength_context, pixel_readout,
                                                   visualization_product)
from cronoscope_pipeline.spectral import (SpectralMappingStatus, inspect_spectral_mapping, spectral_wcs,
                                          wavelength_at_pixel)
from cronoscope_pipeline.spectral_measurements import SpectralRepository
from cronoscope_pipeline.triage import controlled_test7_annotation, presentation
from web_app.moving_objects import MovingObjectCatalog
from web_app.target_resolver import TargetResolver

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).with_name("static")
DISPLAY_FOV_FRACTIONS = {"full": 1.0, "half": 0.5, "quarter": 0.25}

# Genuine Level-2 products deliberately retained in the workspace.  These are
# a small owner-verification set, not an archive search or a synthetic demo.
LOCAL_VIEWER_TARGETS = {
    "r-draconis": {"name": "R Draconis", "path": ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W17_4B_0021_1D3_spx_l2b-v20-2025-240.fits",
                    "detector": "SPHEREx-D3", "wave": (1.6301e-6, 2.4346e-6), "mjd": 60789.880277},
    "barnards-star": {"name": "Barnard's Star", "path": ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W33_2C_0321_1D3_spx_l2b-v20-2025-267.fits",
                       "detector": "SPHEREx-D3", "wave": (1.6301e-6, 2.4346e-6), "mjd": 60902.865381},
    "rw-aur": {"name": "RW Aur", "path": ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W37_2A_0051_1D3_spx_l2b-v20-2025-267.fits",
               "detector": "SPHEREx-D3", "wave": (1.6301e-6, 2.4346e-6), "mjd": 60929.678143},
    "wise-0855-d6": {"name": "WISE 0855", "path": ROOT / "nasa_targets" / "context_0.10deg" / "level2_2026W20_1A_0033_1D6_spx_l2b-v24-2026-135.fits",
                     "detector": "SPHEREx-D6", "wave": (4.4115e-6, 5.0096e-6), "mjd": 61171.096350255,
                     "note": "Contains one non-finite IMAGE pixel; use it to verify invalid-pixel handling."},
}

# Genuine local validation products, grouped only by the owner-facing target
# selector.  These remain separate from frozen LOCAL REPLAY fixtures.
LOCAL_COMPARISON_SOURCES = {
    "r-draconis": ((ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W17_4B_0021_1D3_spx_l2b-v20-2025-240.fits", 60789.880277196, "SPHEREx-D3", (1.6301e-6, 2.4346e-6)),),
    "barnards-star": (
        (ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W33_2C_0321_1D3_spx_l2b-v20-2025-267.fits", 60902.865380749, "SPHEREx-D3", (1.6301e-6, 2.4346e-6)),
        (ROOT / "nasa_targets" / "original_0.03deg" / "level2_2026W19_1A_0403_1D3_spx_l2b-v24-2026-131.fits", 61165.083637763, "SPHEREx-D3", (1.6301e-6, 2.4346e-6)),
    ),
    "rw-aur": ((ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W37_2A_0051_1D3_spx_l2b-v20-2025-267.fits", 60929.678142671, "SPHEREx-D3", (1.6301e-6, 2.4346e-6)),),
    "wise-0855-d6": (
        (ROOT / "nasa_targets" / "original_0.03deg" / "level2_2025W19_1B_0116_1D6_spx_l2b-v20-2025-241.fits", 60800.700694650, "SPHEREx-D6", (4.4115e-6, 5.0096e-6)),
        (ROOT / "nasa_targets" / "original_0.03deg" / "level2_2026W20_1A_0033_1D6_spx_l2b-v24-2026-135.fits", 61171.097016444, "SPHEREx-D6", (4.4115e-6, 5.0096e-6)),
    ),
}


@dataclass(frozen=True)
class ApiLimits:
    max_radius_deg: float = 0.25
    max_products_per_search: int = 500
    max_option_page_size: int = 100
    max_concurrent_comparisons: int = 1
    comparison_timeout_note_seconds: int = 120


def _envelope(operation: str, status: str, *, data: dict[str, Any] | None = None,
              warnings: list[str] | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    return {"operation": operation, "status": status, "data": data or {}, "warnings": warnings or [],
            "errors": errors or [], "provenance": {"orchestrator": ORCHESTRATOR_VERSION,
            "frozen_detector": FROZEN_TEST5_TEST7_V1.identity}, "timings_seconds": {}}


def _browser_safe(value: Any) -> Any:
    """Redact private paths and archive URLs should a backend envelope include them."""
    if isinstance(value, dict):
        return {key: _browser_safe(item) for key, item in value.items()
                if key not in {"cache_path", "source_url", "access_url"}}
    if isinstance(value, list):
        return [_browser_safe(item) for item in value]
    return value


def _local_replay_orchestrator() -> CronoscopeOrchestrator:
    names = ("test7_case1_a.fits", "test7_case1_b.fits")
    records = [ObservationRecord(name, None, None, 61023.0 + index * .001, 61023.001 + index * .001,
                                 1.6301e-6, 2.4346e-6, "SPHEREx-D3", 2, "image",
                                 f"controlled-local-replay://{name}", "image/fits", None,
                                 "spherex_qr2", "SPHEREx", None, None,
                                 raw_identifiers={"controlled_replay_file": name})
               for index, name in enumerate(names)]
    paths = {record.observation_id: ROOT / "fits_files" / str(record.observation_id) for record in records}

    def discovery(*_args: Any, **_kwargs: Any) -> list[ObservationRecord]:
        return records

    def retrieve(record: ObservationRecord, _cache_dir: str) -> RetrievalResult:
        path = paths[record.observation_id]
        return RetrievalResult(RetrievalStatus.CACHE_HIT, str(record.observation_id), str(path), record.access_url,
                               path.stat().st_size, record.observation_id, FitsValidation(True, 7))

    return CronoscopeOrchestrator(discovery_fetcher=discovery, retriever=retrieve, normalizer=normalize_fits_product)


def _local_real_target_orchestrator(target_id: str) -> CronoscopeOrchestrator | None:
    """Expose retained real FITS only for an explicit local target selection."""
    sources = LOCAL_COMPARISON_SOURCES.get(target_id)
    if sources is None or any(not path.is_file() for path, *_rest in sources):
        return None
    records = []
    for path, mjd, detector, wave in sources:
        records.append(ObservationRecord(path.stem, None, None, mjd, mjd, wave[0], wave[1], detector, 2, "image",
                                         f"local-real://{target_id}/{path.name}", "image/fits", None,
                                         "spherex_qr2", "SPHEREx", LOCAL_VIEWER_TARGETS[target_id]["name"], None,
                                         raw_identifiers={"local_real_path": str(path), "local_target_id": target_id}))

    def discovery(*_args: Any, **_kwargs: Any) -> list[ObservationRecord]:
        return records

    def retrieve(record: ObservationRecord, _cache_dir: str) -> RetrievalResult:
        path = Path(str(record.raw_identifiers["local_real_path"]))
        return RetrievalResult(RetrievalStatus.CACHE_HIT, f"local_real_{target_id}_{path.stem}", str(path), record.access_url,
                               path.stat().st_size, record.observation_id, FitsValidation(True, 1))

    return CronoscopeOrchestrator(discovery_fetcher=discovery, retriever=retrieve, normalizer=normalize_fits_product)


def _science_limits(*arrays: Any) -> tuple[float, float]:
    finite = np.concatenate([np.asarray(array, dtype=float)[np.isfinite(np.asarray(array, dtype=float))] for array in arrays])
    if not finite.size:
        return 0.0, 1.0
    low, high = np.percentile(finite, (2, 98))
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        low, high = float(np.min(finite)), float(np.max(finite))
    return float(low), float(high if high > low else low + 1.0)


def _render_science(array: Any, *, limits: tuple[float, float] | None = None) -> bytes:
    values = np.asarray(array, dtype=float)
    low, high = limits or _science_limits(values)
    normalized = np.clip((values - low) / max(high - low, np.finfo(float).eps), 0, 1)
    pixels = np.where(np.isfinite(normalized), normalized, 0) * 255
    image = Image.fromarray(pixels.astype(np.uint8), mode="L")
    output = io.BytesIO(); image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _render_difference(array: Any) -> bytes:
    values = np.asarray(array, dtype=float)
    finite = values[np.isfinite(values)]
    maximum = float(np.percentile(np.abs(finite), 98)) if finite.size else 1.0
    maximum = maximum if np.isfinite(maximum) and maximum > 0 else 1.0
    normalized = np.clip(values / maximum, -1, 1)
    positive, negative = np.clip(normalized, 0, 1), np.clip(-normalized, 0, 1)
    rgb = np.stack((255 * (1 - negative), 255 * (1 - positive - negative), 255 * (1 - positive)), axis=-1)
    rgb[~np.isfinite(values)] = 0
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    output = io.BytesIO(); image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _display_crop(array: Any, field_of_view: str) -> np.ndarray:
    """Return a centred reference-frame display crop without resampling pixels."""
    values = np.asarray(array)
    fraction = DISPLAY_FOV_FRACTIONS[field_of_view]
    height, width = values.shape[:2]
    crop_height, crop_width = max(1, int(height * fraction + .5)), max(1, int(width * fraction + .5))
    top, left = (height - crop_height) // 2, (width - crop_width) // 2
    return values[top:top + crop_height, left:left + crop_width]


def _spectral_status(status: SpectralMappingStatus) -> str:
    """Expose browser vocabulary without concealing unavailable calibration."""
    return {SpectralMappingStatus.VALID: "VALID",
            SpectralMappingStatus.OUTSIDE_SUPPORTED_DOMAIN: "OUTSIDE_MAPPING",
            SpectralMappingStatus.UNAVAILABLE: "MISSING_WCS_WAVE",
            SpectralMappingStatus.MALFORMED: "INVALID_MAPPING",
            SpectralMappingStatus.UNKNOWN_UNITS: "INVALID_MAPPING"}[status]


def _render_wavelength_map(product: Any, field_of_view: str = "full") -> bytes | None:
    """Render an actual WCS-WAVE wavelength coordinate map, never image data."""
    if not product or not product.image_shape:
        return None
    height, width = product.image_shape
    # The WCS table itself is an approximation.  A bounded grid plus nearest
    # neighbour expansion makes that explicit while preserving its coordinates.
    step = max(1, int(max(height, width) / 256))
    ys, xs = np.mgrid[0:height:step, 0:width:step]
    try:
        with fits.open(product.cache_path, memmap=True) as hdul:
            wcs = spectral_wcs(hdul)
            world = wcs.all_pix2world(np.column_stack((xs.ravel(), ys.ravel())), 0)
        values = np.asarray(world[:, 0], dtype=float).reshape(xs.shape)
    except Exception:
        return None
    if not np.isfinite(values).any():
        return None
    low, high = float(np.nanmin(values)), float(np.nanmax(values))
    scaled = np.clip((values - low) / max(high - low, np.finfo(float).eps), 0, 1)
    # Compact deterministic blue→gold colour ramp; no science array involved.
    rgb = np.stack((20 + 235 * scaled, 55 + 150 * scaled, 145 - 100 * scaled), axis=-1).astype(np.uint8)
    image = Image.fromarray(_display_crop(rgb, field_of_view), mode="RGB").resize((int(width * DISPLAY_FOV_FRACTIONS[field_of_view] + .5), int(height * DISPLAY_FOV_FRACTIONS[field_of_view] + .5)), Image.Resampling.NEAREST)
    output = io.BytesIO(); image.save(output, format="PNG", optimize=False); return output.getvalue()


class CronoscopeWebApplication:
    """In-memory HTTP boundary; restart clears product and comparison IDs."""

    def __init__(self, *, live_orchestrator: CronoscopeOrchestrator | None = None,
                 replay_orchestrator: CronoscopeOrchestrator | None = None, limits: ApiLimits = ApiLimits(),
                 moving_catalog: MovingObjectCatalog | None = None, spectral_repository: SpectralRepository | None = None,
                 target_resolver: TargetResolver | None = None) -> None:
        self.live = live_orchestrator or CronoscopeOrchestrator()
        self.replay = replay_orchestrator or _local_replay_orchestrator()
        self.limits = limits
        self._owners: dict[str, CronoscopeOrchestrator] = {}
        self._comparison_owners: dict[str, CronoscopeOrchestrator] = {}
        self._comparison_slots = threading.BoundedSemaphore(limits.max_concurrent_comparisons)
        self.moving_catalog = moving_catalog or MovingObjectCatalog.from_frozen_artifacts()
        self.spectral_repository = spectral_repository or SpectralRepository(ROOT / "spectral_measurements")
        self.target_resolver = target_resolver or TargetResolver()
        self._local_viewer_products: dict[str, Any] = {}

    @staticmethod
    def _viewer_target_summary(target_id: str, item: dict[str, Any]) -> dict[str, Any]:
        filename = Path(item["path"]).name
        release = re.search(r"l2b-v\d+", filename)
        return {"target_id": target_id, "target_name": item["name"], "product_filename": filename,
                "detector": item["detector"], "wavelength_min_um": item["wave"][0] * 1e6,
                "wavelength_max_um": item["wave"][1] * 1e6, "mjd": item["mjd"],
                "release": None if release is None else release.group(0), "note": item.get("note")}

    def _viewer_product(self, target_id: str) -> tuple[Any | None, dict[str, Any] | None]:
        item = LOCAL_VIEWER_TARGETS.get(target_id)
        if item is None:
            return None, None
        cached = self._local_viewer_products.get(target_id)
        if cached is not None:
            return cached, item
        path = Path(item["path"])
        validation = FitsValidation(True, None)
        if not path.is_file():
            return None, item
        record = ObservationRecord(path.stem, None, None, item["mjd"], item["mjd"], item["wave"][0], item["wave"][1],
                                   item["detector"], 2, "image", None, "image/fits", None, "spherex_qr2",
                                   "SPHEREx", item["name"], None, raw_identifiers={"local_product_filename": path.name})
        result = RetrievalResult(RetrievalStatus.CACHE_HIT, f"viewer_{target_id}", str(path), None, path.stat().st_size,
                                 record.observation_id, validation)
        try:
            product = normalize_fits_product(result, record)
        except Exception:
            return None, item
        self._local_viewer_products[target_id] = product
        return product, item

    def _viewer_metadata(self, target_id: str) -> dict[str, Any] | None:
        product, item = self._viewer_product(target_id)
        if product is None or item is None:
            return None
        visual = visualization_product(product)
        payload = visual.to_jsonable(include_display_raster=False)
        payload["wavelength_context"] = inspect_spectral_mapping(product).to_jsonable()
        if product.image_shape:
            center = pixel_readout(product, (product.image_shape[1] - 1) / 2, (product.image_shape[0] - 1) / 2)
            payload["recommended_wavelength_um"] = center.wavelength_context.wavelength_um
        return {"target": self._viewer_target_summary(target_id, item), "visualization": payload,
                "source_spectrum": {"status": "UNAVAILABLE", "message": "Source spectrum unavailable — local WCS-WAVE context only."},
                "provenance": {"source": "Existing local SPHEREx Level-2 FITS", "processing": "cronoscope_pipeline science_interface",
                               "wavelength_context": "FITS IMAGE alternate WCS key W / WAVE-TAB"}}

    def _viewer_image(self, target_id: str) -> bytes | None:
        product, _item = self._viewer_product(target_id)
        if product is None:
            return None
        visual = visualization_product(product)
        if visual.display_raster is None:
            return None
        output = io.BytesIO()
        Image.fromarray(visual.display_raster, mode="L").save(output, format="PNG", optimize=False)
        return output.getvalue()

    def _viewer_pixel(self, target_id: str, x: float, y: float) -> dict[str, Any] | None:
        product, item = self._viewer_product(target_id)
        if product is None or item is None:
            return None
        return {"target": self._viewer_target_summary(target_id, item), "readout": pixel_readout(product, x, y).to_jsonable(),
                "source_spectrum": "Source spectrum unavailable — local WCS-WAVE context only."}

    def _viewer_wavelength_overlay(self, target_id: str, wavelength_um: float, tolerance_um: float) -> dict[str, Any] | None:
        product, item = self._viewer_product(target_id)
        if product is None or item is None:
            return None
        return {"target": self._viewer_target_summary(target_id, item),
                "overlay": highlight_wavelength_context(product, wavelength_um, tolerance_um).to_jsonable()}

    def _viewer_overlap(self, first_id: str, second_id: str) -> dict[str, Any] | None:
        first, first_item = self._viewer_product(first_id); second, second_item = self._viewer_product(second_id)
        if first is None or second is None or first_item is None or second_item is None:
            return None
        if first.wcs is None or second.wcs is None or not first.image_shape or not second.image_shape:
            return {"status": "UNSUPPORTED_WCS", "message": "Wavelength overlay is unsupported because at least one product lacks valid celestial WCS."}
        def sampled_hits(source: Any, destination: Any) -> int:
            height, width = source.image_shape
            hits = 0
            for x, y in ((0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1), ((width - 1) / 2, (height - 1) / 2)):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        warnings.simplefilter("ignore", UserWarning)
                        ra, dec = source.wcs.pixel_to_world_values(x, y)
                        contained = contains_sky_coordinate(destination, float(ra), float(dec))
                    if contained.inside:
                        hits += 1
                except Exception:
                    # An unprojectable sample is not a coverage hit.
                    continue
            return hits
        hits = sampled_hits(first, second) + sampled_hits(second, first)
        same_channel = first.archive_detector == second.archive_detector
        ranges = first.archive_wavelength_m, second.archive_wavelength_m
        ranges_overlap = bool(ranges[0] and ranges[1] and None not in (*ranges[0], *ranges[1]) and
                              max(ranges[0][0], ranges[1][0]) <= min(ranges[0][1], ranges[1][1]))
        if hits == 0:
            status, message = "UNSUPPORTED_NO_CELESTIAL_COVERAGE", "No sampled shared celestial coverage; no cross-product wavelength overlay is rendered."
        elif not (same_channel or ranges_overlap):
            status, message = "UNSUPPORTED_DIFFERENT_WAVELENGTH", "Products overlap on the sky but have incompatible archive wavelength ranges."
        else:
            status, message = "SUPPORTED_SAMPLED_COVERAGE", "Sampled celestial coverage and wavelength context permit a geometric overlay; this is not a spectrum or calibrated composite."
        return {"status": status, "message": message, "sampled_coverage_hits": hits,
                "first": self._viewer_target_summary(first_id, first_item), "second": self._viewer_target_summary(second_id, second_item),
                "same_archive_channel": same_channel, "archive_wavelength_ranges_overlap": ranges_overlap}

    def _reply(self, start_response: Callable[..., Any], status: str, body: bytes, content_type: str) -> list[bytes]:
        start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")])
        return [body]

    def _json(self, start_response: Callable[..., Any], payload: dict[str, Any], http_status: str = "200 OK") -> list[bytes]:
        return self._reply(start_response, http_status, json.dumps(_browser_safe(payload), allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self, environ: dict[str, Any]) -> dict[str, Any]:
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if length > 32_768:
                raise ValueError("Request body exceeds 32 KB")
            payload = json.loads(environ["wsgi.input"].read(length or 0) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid JSON request: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON request must be an object")
        return payload

    @staticmethod
    def _number(payload: dict[str, Any], name: str) -> float:
        value = payload.get(name)
        if isinstance(value, bool):
            raise ValueError(f"{name} must be numeric")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc

    def _search(self, payload: dict[str, Any], orchestrator: CronoscopeOrchestrator, *, mode: str) -> dict[str, Any]:
        try:
            ra, dec, radius = (self._number(payload, key) for key in ("ra_deg", "dec_deg", "radius_deg"))
        except ValueError as exc:
            return _envelope("search_sky", "INVALID_COORDINATE", errors=[str(exc)])
        if not np.isfinite(ra) or not np.isfinite(dec) or not np.isfinite(radius) or not (0 <= ra < 360) or not (-90 <= dec <= 90) or radius <= 0:
            return _envelope("search_sky", "INVALID_COORDINATE", errors=["RA must be [0, 360), Dec [-90, 90], and radius positive."])
        if radius > self.limits.max_radius_deg:
            return _envelope("search_sky", "SEARCH_RADIUS_LIMIT", errors=[f"Maximum radius is {self.limits.max_radius_deg} degrees."],
                             warnings=["No search was run; narrow the requested sky area."])
        requested_collection = payload.get("collection", DEFAULT_COLLECTION)
        if mode != "LIVE":
            requested_collection = "spherex_qr2"
        if not isinstance(requested_collection, str) or requested_collection not in SUPPORTED_COLLECTIONS:
            return _envelope("search_sky", "INVALID_COLLECTION", errors=[f"collection must be one of: {supported_collections_text()}"])
        result = orchestrator.search_sky(ra, dec, radius, label="LOCAL_REPLAY" if mode == "LOCAL_REPLAY" else None,
                                         collection=requested_collection)
        if result["status"] != "SUCCESS":
            return result
        ids = [product["product_id"] for product in result["data"]["products"]]
        if len(ids) > self.limits.max_products_per_search:
            orchestrator.forget_records(ids)
            return _envelope("search_sky", "PRODUCT_LIMIT_EXCEEDED", data={"product_count": len(ids), "retained_product_count": 0},
                             errors=[f"Search returned {len(ids)} products; the limit is {self.limits.max_products_per_search}."],
                             warnings=["No products were retained. Narrow the search; results were not silently truncated."])
        self._owners.update({product_id: orchestrator for product_id in ids})
        result["data"]["mode"] = mode
        if mode == "LOCAL_REPLAY":
            result["warnings"].append("LOCAL REPLAY: saved Test 7 artifacts, not a live IRSA query.")
        return result

    def _resolve_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.target_resolver.resolve(payload.get("target"))
        if result.status not in {"RESOLVED_LOCAL", "RESOLVED_LIVE"}:
            return _envelope("resolve_target", result.status, data={"resolution": result.to_jsonable()}, errors=[result.message] if result.message else [])
        warnings = ["Bundled local catalog result; no live resolver request was made."] if result.cached else []
        return _envelope("resolve_target", "SUCCESS", data={"resolution": result.to_jsonable()}, warnings=warnings)

    def _local_real_target_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        target_id = payload.get("target_id")
        if not isinstance(target_id, str) or target_id not in LOCAL_COMPARISON_SOURCES:
            return _envelope("local_real_target_search", "INVALID_TARGET", errors=["Choose a known local viewer target."])
        orchestrator = _local_real_target_orchestrator(target_id)
        if orchestrator is None:
            return _envelope("local_real_target_search", "LOCAL_PRODUCT_UNAVAILABLE", errors=["The retained local FITS product is unavailable."])
        result = orchestrator.search_sky(0.0, 0.0, 0.0001, label=f"LOCAL_REAL_{target_id}", collection="spherex_qr2")
        ids = [product["product_id"] for product in result.get("data", {}).get("products", [])]
        self._owners.update({product_id: orchestrator for product_id in ids})
        result["operation"] = "local_real_target_search"
        result["data"]["mode"] = "LOCAL_REAL_PRODUCTS"
        result["data"]["local_target_id"] = target_id
        result["warnings"].append("LOCAL REAL PRODUCTS: retained genuine FITS only; this is separate from frozen LOCAL REPLAY.")
        return result

    def _owner_for(self, product_ids: list[str], operation: str) -> tuple[CronoscopeOrchestrator | None, dict[str, Any] | None]:
        owners = {self._owners.get(product_id) for product_id in product_ids}
        if None in owners or len(owners) != 1:
            return None, _envelope(operation, "INVALID_PRODUCT_ID", errors=["Unknown, stale, or mixed-session product ID."])
        return owners.pop(), None

    def _options(self, payload: dict[str, Any]) -> dict[str, Any]:
        ids = payload.get("product_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item.startswith("spx_") for item in ids):
            return _envelope("list_comparison_options", "INVALID_REQUEST", errors=["product_ids must be non-empty opaque spx_ IDs."])
        try:
            offset, limit = int(payload.get("offset", 0)), int(payload.get("limit", 50))
        except (TypeError, ValueError):
            return _envelope("list_comparison_options", "INVALID_REQUEST", errors=["offset and limit must be integers."])
        if limit > self.limits.max_option_page_size:
            return _envelope("list_comparison_options", "OPTION_PAGE_LIMIT", errors=[f"Maximum option page size is {self.limits.max_option_page_size}."],
                             warnings=["No options were silently truncated; request a smaller page."])
        owner, error = self._owner_for(ids, "list_comparison_options")
        return error or owner.list_comparison_options(ids, offset=offset, limit=limit)

    def _compare(self, payload: dict[str, Any]) -> dict[str, Any]:
        ids = [payload.get("product_a_id"), payload.get("product_b_id")]
        if not all(isinstance(item, str) and item.startswith("spx_") for item in ids):
            return _envelope("compare_selected_products", "INVALID_REQUEST", errors=["Two opaque product IDs are required."])
        owner, error = self._owner_for(ids, "compare_selected_products")
        if error:
            return error
        if not self._comparison_slots.acquire(blocking=False):
            return _envelope("compare_selected_products", "COMPARISON_BUSY", errors=["A comparison is already running; try again shortly."],
                             warnings=[f"Expensive comparisons are limited to {self.limits.max_concurrent_comparisons} at a time."])
        try:
            result = owner.prepare_selected_products(ids[0], ids[1])
        finally:
            self._comparison_slots.release()
        comparison_id = result.get("data", {}).get("comparison_id")
        if comparison_id:
            self._comparison_owners[comparison_id] = owner
        return result

    def _image(self, comparison_id: str, image_kind: str, field_of_view: str = "full") -> bytes | None:
        owner = self._comparison_owners.get(comparison_id)
        artifact = owner.comparison_artifact(comparison_id) if owner else None
        image_a, image_b = getattr(artifact, "science_image_a", None), getattr(artifact, "registered_image_b", None)
        if image_kind == "wavelength-a":
            return _render_wavelength_map(getattr(artifact, "product_a", None), field_of_view)
        if image_kind == "wavelength-b":
            return _render_wavelength_map(getattr(artifact, "product_b", None), field_of_view)
        arrays = {"a": image_a, "b": image_b, "difference": getattr(artifact, "difference_image", None),
                  "blink-a": image_a, "blink-b": image_b}
        array = arrays.get(image_kind)
        if array is None:
            return None
        array = _display_crop(array, field_of_view)
        if image_kind == "difference":
            return _render_difference(array)
        shared_limits = _science_limits(_display_crop(image_a, field_of_view), _display_crop(image_b, field_of_view)) if image_kind.startswith("blink-") else None
        return _render_science(array, limits=shared_limits)

    def _spectral_probe(self, comparison_id: str, x: float, y: float) -> dict[str, Any] | None:
        """Sky-lock a reference-grid click, then evaluate each native product."""
        owner = self._comparison_owners.get(comparison_id)
        artifact = owner.comparison_artifact(comparison_id) if owner else None
        a, b = getattr(artifact, "product_a", None), getattr(artifact, "product_b", None)
        if artifact is None or a is None or b is None or not artifact.output_shape:
            return None
        height, width = artifact.output_shape
        if not (0 <= x < width and 0 <= y < height):
            return {"status": "OUTSIDE_MAPPING", "warning": "Displayed reference pixel is outside comparison frame."}
        try:
            ra, dec = (float(v) for v in a.wcs.pixel_to_world_values(x, y))
            ax, ay = (float(v) for v in a.wcs.world_to_pixel_values(ra, dec))
            bx, by = (float(v) for v in b.wcs.world_to_pixel_values(ra, dec))
        except Exception as exc:
            return {"status": "TRANSFORM_ERROR", "warning": str(exc)}

        def observation(product: Any, px: float, py: float) -> dict[str, Any]:
            result = wavelength_at_pixel(product, px, py)
            return {"status": _spectral_status(result.status), "product_identity": product.cache_identity,
                    "observation_id": product.observation_id, "detector": product.archive_detector,
                    "native_pixel": {"x": px, "y": py}, "wavelength_um": result.wavelength_um,
                    "bandwidth_um": result.bandwidth_um, "archive_em_min_m": product.archive_wavelength_m[0] if product.archive_wavelength_m else None,
                    "archive_em_max_m": product.archive_wavelength_m[1] if product.archive_wavelength_m else None,
                    "spectral_mapping_source": "FITS IMAGE alternate WCS key W / WAVE-TAB",
                    "warning": result.warning or "Approximate tabular WCS calibration."}
        first, second = observation(a, ax, ay), observation(b, bx, by)
        delta = None if first["status"] != "VALID" or second["status"] != "VALID" else abs(first["wavelength_um"] - second["wavelength_um"])
        return {"status": "VALID" if first["status"] == second["status"] == "VALID" else "PARTIAL",
                "comparison_id": comparison_id, "display_pixel": {"x": x, "y": y},
                "sky_position": {"ra_deg": ra, "dec_deg": dec}, "observation_a": first, "observation_b": second,
                "wavelength_difference_um": delta,
                "coordinate_path": "reference A display pixel → RA/Dec → independent native A/B pixels → WCS-WAVE"}

    def _triage(self, comparison_id: str) -> dict[str, Any] | None:
        owner = self._comparison_owners.get(comparison_id)
        artifact = owner.comparison_artifact(comparison_id) if owner else None
        if artifact is None:
            return None
        replay = owner is self.replay
        rows = [presentation(candidate, controlled_test7_annotation(candidate) if replay else None)
                for candidate in artifact.candidates]
        return {"comparison_id": comparison_id, "detector_candidate_count": len(rows), "candidates": rows,
                "candidate_analysis_status": artifact.candidate_analysis_status,
                "triage_notice": "Presentation sorting and filters never change detector candidates, scores, or validation provenance."}

    def _candidate_cutout(self, comparison_id: str, candidate_id: str) -> bytes | None:
        triage = self._triage(comparison_id)
        owner = self._comparison_owners.get(comparison_id)
        artifact = owner.comparison_artifact(comparison_id) if owner else None
        if triage is None or artifact is None:
            return None
        try:
            rank = int(candidate_id.removeprefix("cand_"))
            candidate = artifact.candidates[rank - 1]
            if candidate.rank != rank: return None
        except (ValueError, IndexError):
            return None
        image = np.asarray(artifact.difference_image, dtype=float)
        pad = 14; xs = (candidate.negative.x, candidate.positive.x); ys = (candidate.negative.y, candidate.positive.y)
        left, right = max(0, int(np.floor(min(xs) - pad))), min(image.shape[1], int(np.ceil(max(xs) + pad)))
        top, bottom = max(0, int(np.floor(min(ys) - pad))), min(image.shape[0], int(np.ceil(max(ys) + pad)))
        rendered = Image.open(io.BytesIO(_render_difference(image[top:bottom, left:right]))).convert("RGB")
        draw = ImageDraw.Draw(rendered)
        for blob, color in ((candidate.negative, "#4d96ff"), (candidate.positive, "#ff5468")):
            x, y = blob.x - left, blob.y - top; draw.ellipse((x - 3, y - 3, x + 3, y + 3), outline=color, width=2)
        draw.line((candidate.negative.x-left, candidate.negative.y-top, candidate.positive.x-left, candidate.positive.y-top), fill="#f8f3a3", width=1)
        output = io.BytesIO(); rendered.save(output, format="PNG", optimize=False); return output.getvalue()

    def _moving_object_image(self, asteroid_id: str, role: str) -> tuple[bytes | None, str | None]:
        """Render a small SPHEREx cutout at a frozen Horizons prediction.

        This is visualization-only retrieval/normalization. It does not form a
        difference image or execute a detector calculation.
        """
        item = self.moving_catalog.observation_for_image(asteroid_id, role)
        if item is None:
            return None, "Unknown target, role, or archive observation."
        record, observation = item
        retrieved = retrieve_product(record, ROOT / ".cronoscope_cache" / "moving_explorer", timeout_seconds=90)
        if not retrieved.succeeded:
            return None, f"SPHEREx image retrieval unavailable: {retrieved.status.value}."
        try:
            product = normalize_fits_product(retrieved, record)
            if product.image is None or product.wcs is None:
                return None, "SPHEREx FITS image or celestial WCS is unavailable."
            x, y = (float(value) for value in product.wcs.world_to_pixel_values(observation["sky_position"]["ra_deg"], observation["sky_position"]["dec_deg"]))
            image = np.asarray(product.image, dtype=float)
            half = 80
            left, right = max(0, int(round(x)) - half), min(image.shape[1], int(round(x)) + half)
            top, bottom = max(0, int(round(y)) - half), min(image.shape[0], int(round(y)) + half)
            if left >= right or top >= bottom:
                return None, "Predicted Horizons coordinate is outside the available SPHEREx image."
            rendered = Image.open(io.BytesIO(_render_science(image[top:bottom, left:right]))).convert("RGB")
            draw = ImageDraw.Draw(rendered)
            px, py = x - left, y - top
            draw.ellipse((px - 5, py - 5, px + 5, py + 5), outline="#ffcf70", width=2)
            draw.line((px - 9, py, px + 9, py), fill="#ffcf70", width=1)
            draw.line((px, py - 9, px, py + 9), fill="#ffcf70", width=1)
            output = io.BytesIO(); rendered.save(output, format="PNG", optimize=False)
            return output.getvalue(), None
        except Exception as exc:
            return None, f"SPHEREx cutout rendering unavailable: {exc}"

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        parsed = urlparse(environ.get("PATH_INFO", "/"))
        path, query, method = parsed.path, parse_qs(parsed.query or environ.get("QUERY_STRING", "")), environ.get("REQUEST_METHOD", "GET").upper()
        if method == "GET" and path == "/api/viewer/targets":
            return self._json(start_response, _envelope("viewer_targets", "SUCCESS", data={"targets": [
                self._viewer_target_summary(target_id, item) for target_id, item in LOCAL_VIEWER_TARGETS.items()
            ], "source_spectrum": "Source spectrum unavailable — local WCS-WAVE context only."}))
        if method == "GET" and path.startswith("/api/viewer/"):
            parts = path.split("/")
            if len(parts) == 5 and parts[4] == "metadata":
                data = self._viewer_metadata(parts[3])
                if data is not None:
                    return self._json(start_response, _envelope("viewer_metadata", "SUCCESS", data=data))
            if len(parts) == 5 and parts[4] == "image":
                body = self._viewer_image(parts[3])
                if body is not None:
                    return self._reply(start_response, "200 OK", body, "image/png")
            if len(parts) == 7 and parts[4] == "pixel":
                try:
                    data = self._viewer_pixel(parts[3], float(parts[5]), float(parts[6]))
                except ValueError:
                    data = None
                if data is not None:
                    return self._json(start_response, _envelope("viewer_pixel", data["readout"]["status"], data=data))
            if len(parts) == 5 and parts[4] == "wavelength-overlay":
                try:
                    wavelength = float(query.get("wavelength_um", [""])[0])
                    tolerance = float(query.get("tolerance_um", [""])[0])
                    data = self._viewer_wavelength_overlay(parts[3], wavelength, tolerance)
                except (TypeError, ValueError):
                    data = None
                if data is not None:
                    return self._json(start_response, _envelope("viewer_wavelength_overlay", data["overlay"]["status"], data=data))
            if len(parts) == 6 and parts[4] == "overlap":
                data = self._viewer_overlap(parts[3], parts[5])
                if data is not None:
                    return self._json(start_response, _envelope("viewer_wavelength_overlap", data["status"], data=data))
            return self._json(start_response, _envelope("viewer", "NOT_FOUND", errors=["Unknown local viewer target or route."]), "404 Not Found")
        if method == "GET" and path == "/api/moving-objects":
            return self._json(start_response, _envelope("list_moving_targets", "SUCCESS", data={"targets": self.moving_catalog.target_summaries(), "source": "Frozen Phase-40D moving-object catalog"}))
        if method == "GET" and path.startswith("/api/moving-objects/"):
            parts = path.split("/")
            if len(parts) == 4 and parts[3].isdigit():
                detail = self.moving_catalog.detail(parts[3])
                if detail is not None:
                    return self._json(start_response, _envelope("moving_target_detail", "SUCCESS", data=detail))
            if len(parts) == 6 and parts[3].isdigit() and parts[4] == "image" and parts[5] in {"old", "new"}:
                body, error = self._moving_object_image(parts[3], parts[5])
                if body is not None:
                    return self._reply(start_response, "200 OK", body, "image/png")
                return self._json(start_response, _envelope("moving_target_image", "UNAVAILABLE", errors=[error or "Image unavailable."]), "503 Service Unavailable")
            return self._json(start_response, _envelope("moving_target", "NOT_FOUND", errors=["Unknown moving target route."]), "404 Not Found")
        if method == "GET" and path.startswith("/api/spectra/"):
            spectrum_id = path.removeprefix("/api/spectra/")
            if spectrum_id and "/" not in spectrum_id:
                spectrum = self.spectral_repository.get(spectrum_id)
                http_status = "200 OK" if spectrum.status.value == "AVAILABLE" else "404 Not Found"
                return self._json(start_response, _envelope("get_spectrum", spectrum.status.value,
                                  data=spectrum.to_jsonable(), warnings=[spectrum.warning] if spectrum.warning else []), http_status)
            return self._json(start_response, _envelope("get_spectrum", "INVALID_REQUEST", errors=["Spectrum ID must be a single filename-safe path segment."]), "400 Bad Request")
        if method == "GET" and path.startswith("/api/image/"):
            parts = path.split("/")
            if len(parts) == 6 and parts[4] == "candidate":
                body = self._candidate_cutout(parts[3], parts[5])
                if body is not None:
                    return self._reply(start_response, "200 OK", body, "image/png")
            if len(parts) == 5:
                field_of_view = query.get("fov", ["full"])[0]
                if field_of_view not in DISPLAY_FOV_FRACTIONS:
                    return self._json(start_response, _envelope("image", "INVALID_DISPLAY_FOV", errors=["fov must be full, half, or quarter."]), "400 Bad Request")
                body = self._image(parts[3], parts[4], field_of_view)
                if body is not None:
                    return self._reply(start_response, "200 OK", body, "image/png")
            return self._json(start_response, _envelope("image", "UNKNOWN_COMPARISON_ID", errors=["Unknown comparison/image ID."]), "404 Not Found")
        if method == "GET" and path.startswith("/api/comparison/") and path.endswith("/triage"):
            parts = path.split("/")
            if len(parts) == 5:
                data = self._triage(parts[3])
                if data is not None:
                    return self._json(start_response, _envelope("candidate_triage", "SUCCESS", data=data))
            return self._json(start_response, _envelope("candidate_triage", "UNKNOWN_COMPARISON_ID", errors=["Unknown comparison ID."]), "404 Not Found")
        if method == "GET" and path.startswith("/api/comparison/") and "/spectral/" in path:
            parts = path.split("/")
            if len(parts) == 7:
                try:
                    data = self._spectral_probe(parts[3], float(parts[5]), float(parts[6]))
                except ValueError:
                    data = {"status": "TRANSFORM_ERROR", "warning": "x and y must be numeric."}
                if data is not None:
                    return self._json(start_response, _envelope("spectral_probe", data.get("status", "VALID"), data=data))
            return self._json(start_response, _envelope("spectral_probe", "UNKNOWN_COMPARISON_ID", errors=["Unknown comparison ID."]), "404 Not Found")
        if method == "GET" and path == "/api/health":
            return self._json(start_response, _envelope("health", "SUCCESS", data={"application": "CRONOSCOPE", "backend_version": ORCHESTRATOR_VERSION,
                              "detector_version": FROZEN_TEST5_TEST7_V1.identity, "capabilities": {"live_search": True, "local_replay": True},
                              "limits": {"max_radius_deg": self.limits.max_radius_deg, "max_products_per_search": self.limits.max_products_per_search,
                                         "max_option_page_size": self.limits.max_option_page_size, "max_concurrent_comparisons": self.limits.max_concurrent_comparisons,
                                         "comparison_timeout_note_seconds": self.limits.comparison_timeout_note_seconds},
                              "display": {"blink_scaling": "A and registered B share one combined 2nd–98th percentile display range; this is read-only.",
                                          "difference_scaling": "Difference uses a symmetric 98th-percentile absolute display range around zero."},
                              "restart_behavior": "Product and comparison IDs are in-memory and expire when the server restarts."}))
        if method == "POST" and path in {"/api/resolve-target", "/api/search", "/api/replay/search", "/api/local-real-target/search", "/api/comparison-options", "/api/compare"}:
            try:
                payload = self._read_json(environ)
            except ValueError as exc:
                return self._json(start_response, _envelope("request", "INVALID_REQUEST", errors=[str(exc)]), "400 Bad Request")
            if path == "/api/resolve-target": result = self._resolve_target(payload)
            elif path == "/api/search": result = self._search(payload, self.live, mode="LIVE")
            elif path == "/api/replay/search": result = self._search(payload, self.replay, mode="LOCAL_REPLAY")
            elif path == "/api/local-real-target/search": result = self._local_real_target_search(payload)
            elif path == "/api/comparison-options": result = self._options(payload)
            else: result = self._compare(payload)
            return self._json(start_response, result)
        if method == "GET":
            requested = "index.html" if path == "/" else path.removeprefix("/")
            # Keep the browser contract explicit: all shell assets live below
            # /static/, while / continues to return the application document.
            if requested.startswith("static/"):
                requested = requested.removeprefix("static/")
            target = (STATIC_DIR / requested).resolve()
            content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
                             ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".mp4": "video/mp4"}
            if target.is_relative_to(STATIC_DIR.resolve()) and target.is_file() and target.suffix.lower() in content_types:
                content_type = content_types[target.suffix.lower()]
                return self._reply(start_response, "200 OK", target.read_bytes(), content_type)
        return self._json(start_response, _envelope("request", "NOT_FOUND", errors=["Route not found."]), "404 Not Found")


def create_app(**kwargs: Any) -> CronoscopeWebApplication:
    return CronoscopeWebApplication(**kwargs)


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    print("CRONOSCOPE local server: http://127.0.0.1:8000")
    make_server("127.0.0.1", 8000, create_app()).serve_forever()
