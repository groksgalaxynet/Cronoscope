"""Controlled service boundary around the verified DR1 cube reader."""

from __future__ import annotations

import hashlib
import json
import resource
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

import numpy as np
import requests

from research.dr1_cube_range.persistent_ledger import PersistentBudgetExceeded
from research.dr1_cube_range.range_cube import (
    BoundedRangeClient,
    ProductIdentity,
    RangeExperimentError,
    RangeResponseError,
)
from research.dr1_cube_reader.reader import (
    CubeReader,
    EvidenceUnavailableError,
    RegionRequest,
    UnsupportedCubeError,
)

from .budgets import BudgetController
from .cache import RangeCache
from .errors import ServiceError
from .resolver import AllowedProduct, OFFICIAL_HOST, ProductResolver
from .schemas import SampleRequest


class RangeSource(Protocol):
    identity: ProductIdentity
    mode: str
    network_requests: int
    network_bytes: int

    def get(self, url: str, start: int, end: int) -> bytes: ...


@dataclass(frozen=True)
class _Segment:
    start: int
    end: int
    data: bytes


class GenuineEvidenceSource:
    """Read-only source over the preserved DR1.5 genuine response ranges."""

    mode = "saved-genuine-dr15-evidence"
    network_requests = 0
    network_bytes = 0

    def __init__(self, root: Path | str, product: AllowedProduct) -> None:
        self.root = Path(root)
        result_path = self.root / "multi_channel_result.json"
        response_root = self.root / "artifacts" / "responses"
        if not result_path.is_file() or not response_root.is_dir():
            raise EvidenceUnavailableError("preserved genuine DR1.5 evidence is incomplete")
        self.reference = json.loads(result_path.read_text(encoding="utf-8"))
        identity = self.reference.get("product_identity", {})
        if identity.get("final_url") != product.url or identity.get("content_length") != product.expected_content_length:
            raise EvidenceUnavailableError("evidence product identity does not match the allowlist")
        self.identity = ProductIdentity(
            identity["final_url"], identity["content_length"],
            identity.get("last_modified"), identity.get("etag"),
        )
        self.segments: list[_Segment] = []
        for metadata_path in sorted(response_root.glob("request_*_bytes_*.json")):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            data_path = metadata_path.with_suffix(".bin")
            data = data_path.read_bytes()
            if len(data) != metadata.get("content_length"):
                raise EvidenceUnavailableError("saved response length failed integrity validation")
            if hashlib.sha256(data).hexdigest() != metadata.get("sha256"):
                raise EvidenceUnavailableError("saved response hash failed integrity validation")
            self.segments.append(_Segment(int(metadata["start"]), int(metadata["end"]), data))
        if not self.segments:
            raise EvidenceUnavailableError("no genuine range responses are available")
        self.segment_hits = 0

    def get(self, url: str, start: int, end: int) -> bytes:
        if url != self.identity.final_url:
            raise EvidenceUnavailableError("reader requested a product outside preserved evidence")
        for segment in self.segments:
            if segment.start <= start and end <= segment.end:
                self.segment_hits += 1
                offset = start - segment.start
                return segment.data[offset:offset + end - start + 1]
        raise EvidenceUnavailableError(
            "the requested range is absent from preserved genuine evidence; no value was fabricated"
        )

    def reference_matches(self, request: SampleRequest, result: dict[str, Any]) -> bool:
        for sample in self.reference.get("samples", []):
            expected = sample.get("request", {})
            key = (
                expected.get("channel_zero_based"), expected.get("x"), expected.get("y"),
                expected.get("width"), expected.get("height"),
            )
            actual = (request.channel, request.x, request.y, request.width, request.height)
            if key != actual:
                continue
            arrays_match = all(
                sample["arrays"][name]["values"] == result["arrays"][name]["values"]
                for name in ("IMAGE", "NHITS", "FLAGS")
            )
            return arrays_match and sample["science"]["channel"] == result["science"]["channel"]
        raise EvidenceUnavailableError("no genuine reference sample exists for the requested selection")


class NoRedirectAllowlistedSession:
    """Requests adapter that never follows redirects or accepts another host."""

    def __init__(self, approved_url: str, session: requests.Session | None = None) -> None:
        self.approved_url = approved_url
        self.session = session or requests.Session()

    def _validate(self, url: str) -> None:
        parsed = urlparse(url)
        if url != self.approved_url or parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST:
            raise RangeResponseError("outbound URL is outside the fixed product allowlist")

    @staticmethod
    def _reject_redirect(response: Any) -> Any:
        if 300 <= response.status_code < 400:
            response.close()
            raise RangeResponseError("archive redirects are forbidden by the product allowlist")
        return response

    def head(self, url: str, **kwargs: Any) -> Any:
        self._validate(url)
        kwargs["allow_redirects"] = False
        return self._reject_redirect(self.session.head(url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> Any:
        self._validate(url)
        kwargs["allow_redirects"] = False
        return self._reject_redirect(self.session.get(url, **kwargs))


class LiveAllowlistedSource:
    """Server-only live range source; never constructed from client URLs."""

    mode = "bounded-allowlisted-http-range"

    def __init__(
        self, product: AllowedProduct, budgets: BudgetController, artifact_dir: Path,
        *, session: requests.Session | None = None,
    ) -> None:
        safe_session = NoRedirectAllowlistedSession(product.url, session)
        self.ledger = budgets.ledger
        self.client = BoundedRangeClient(
            self.ledger, session=safe_session, artifact_dir=artifact_dir
        )
        self.identity = self.client.head(product.url)
        if self.identity.final_url != product.url:
            raise UnsupportedCubeError("archive product URL changed")
        if self.identity.content_length != product.expected_content_length:
            raise UnsupportedCubeError("archive product size changed")

    @property
    def network_requests(self) -> int:
        return self.ledger.snapshot(include_requests=False)["attempts"]

    @property
    def network_bytes(self) -> int:
        return self.ledger.snapshot(include_requests=False)["actual_received_bytes"]

    def get(self, url: str, start: int, end: int) -> bytes:
        if url != self.identity.final_url:
            raise RangeResponseError("reader URL differs from the allowlisted identity")
        if end - start + 1 > 1024 * 1024:
            raise RangeResponseError("a single range may not exceed 1 MiB")
        return self.client.get(url, start, end)


class CachedRangeSource:
    """Exact-range cache wrapper preserving the underlying source identity."""

    def __init__(self, source: RangeSource, cache: RangeCache) -> None:
        self.source = source
        self.cache = cache
        self.identity = source.identity
        self.mode = f"cached:{source.mode}"

    @property
    def network_requests(self) -> int:
        return self.source.network_requests

    @property
    def network_bytes(self) -> int:
        return self.source.network_bytes

    @property
    def cache_hits(self) -> int:
        return self.cache.hits

    def get(self, url: str, start: int, end: int) -> bytes:
        if url != self.identity.final_url:
            raise EvidenceUnavailableError("cache request product identity mismatch")
        return self.cache.get_or_fetch(
            url, self.identity.content_length, start, end,
            lambda: self.source.get(url, start, end),
        )


@dataclass(frozen=True)
class ServiceConfig:
    state_dir: Path
    evidence_root: Path | None = None
    enable_live: bool = False
    cache_max_bytes: int = 2 * 1024 * 1024
    max_concurrent_retrievals: int = 1


class CubeSampleService:
    """One-product, one-channel, bounded-region experimental service."""

    def __init__(
        self, config: ServiceConfig, *,
        source_factory: Callable[[AllowedProduct], RangeSource] | None = None,
    ) -> None:
        if config.max_concurrent_retrievals != 1:
            raise ValueError("DR1.6 permits exactly one concurrent archive retrieval")
        if config.evidence_root is None and not config.enable_live and source_factory is None:
            raise ValueError("service requires preserved evidence or explicit live enablement")
        self.config = config
        self.resolver = ProductResolver()
        self.budgets = BudgetController(config.state_dir)
        self.cache = RangeCache(config.state_dir / "range_cache", max_bytes=config.cache_max_bytes)
        self._slot = threading.BoundedSemaphore(1)
        self._source_factory = source_factory

    def _source(self, product: AllowedProduct) -> RangeSource:
        if self._source_factory is not None:
            return self._source_factory(product)
        if self.config.evidence_root is not None:
            return GenuineEvidenceSource(self.config.evidence_root, product)
        if not self.config.enable_live:
            raise ServiceError("LIVE_ACCESS_DISABLED", "Live archive access is disabled.", 503)
        return LiveAllowlistedSource(
            product, self.budgets, self.config.state_dir / "archive_artifacts"
        )

    def sample(self, payload: object) -> dict[str, Any]:
        request = SampleRequest.parse(payload)
        product = self.resolver.resolve(request.product_id)
        if not self._slot.acquire(blocking=False):
            raise ServiceError(
                "RETRIEVAL_BUSY", "The single experimental archive retrieval slot is busy.", 429
            )
        started = time.perf_counter()
        before = self.budgets.public_snapshot()
        cache_before = self.cache.stats()
        try:
            raw_source = self._source(product)
            if raw_source.identity.final_url != product.url:
                raise ServiceError("PRODUCT_IDENTITY_MISMATCH", "Resolved product URL changed.", 502)
            if raw_source.identity.content_length != product.expected_content_length:
                raise ServiceError("PRODUCT_SIZE_MISMATCH", "Resolved product size changed.", 502)
            source = CachedRangeSource(raw_source, self.cache)
            reader = CubeReader(source).open()
            result = reader.read_region(
                RegionRequest(request.channel, request.x, request.y, request.width, request.height)
            )
            if tuple(result["provenance"]["hdu_sequence"]) != product.expected_hdu_sequence:
                raise ServiceError("UNSUPPORTED_FITS_LAYOUT", "FITS extension layout is not allowlisted.", 422)
            genuine_match: bool | None = None
            if isinstance(raw_source, GenuineEvidenceSource):
                genuine_match = raw_source.reference_matches(request, result)
                if not genuine_match:
                    raise ServiceError("GENUINE_EVIDENCE_MISMATCH", "Decoded values disagree with preserved evidence.", 500)
            after = self.budgets.public_snapshot()
            cache_after = self.cache.stats()
            pixels = request.width * request.height
            missing = {
                name: pixels - int(result["arrays"][name]["finite_count"])
                for name in ("IMAGE", "NHITS", "FLAGS")
            }
            return {
                "classification": "EXPERIMENTAL_DR1_CUBE_SAMPLE",
                "status": "SUCCESS",
                "product": {
                    "product_id": product.product_id,
                    "filename": product.filename,
                    "release": product.release,
                    "collection": product.collection,
                    "official_url": product.url,
                    "content_length": product.expected_content_length,
                    "last_modified": raw_source.identity.last_modified,
                    "etag": raw_source.identity.etag,
                },
                "selection": {
                    "channel_zero_based": request.channel,
                    "pixel_origin_zero_based": [request.x, request.y],
                    "width": request.width,
                    "height": request.height,
                },
                "wavelength_metadata": result["science"]["channel"],
                "arrays": result["arrays"],
                "missing_data": {
                    "null_represents_nonfinite": True,
                    "missing_count": missing,
                    "blank_channels_unavailable": [51, 52],
                },
                "science": {
                    "image_unit": result["science"]["image_unit"],
                    "nhits_meaning": "observation contribution count; not uncertainty",
                    "flags_semantics": "raw uninterpreted integer bitmap",
                    "uncertainty": None,
                    "product_class": "DR1 all-sky coadded spectral cube",
                    "source_photometry": False,
                    "source_spectrum": False,
                    "time_series": False,
                },
                "fits_provenance": {
                    "hdu_sequence": result["provenance"]["hdu_sequence"],
                    "header_sha256": result["provenance"]["header_sha256"],
                    "range_sha256": {
                        name: result["ranges"][name]["sha256"]
                        for name in ("IMAGE", "NHITS", "FLAGS")
                    },
                    "axis_order": result["coordinates"]["numpy_axis_order"],
                },
                "validation": {
                    "reader_classification": result["validation"]["classification"],
                    "genuine_evidence_match": genuine_match,
                    "independent_photometric_calibration": False,
                },
                "resources": {
                    "external_requests_this_call": after["attempts"] - before["attempts"],
                    "external_bytes_this_call": after["actual_received_bytes"] - before["actual_received_bytes"],
                    "budget": after,
                    "cache": cache_after,
                    "cache_hits_this_call": cache_after["hits"] - cache_before["hits"],
                    "runtime_seconds": time.perf_counter() - started,
                    "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                },
                "limitations": result["limitations"] + [
                    "Decoder agreement does not establish independent photometric calibration."
                ],
            }
        except ServiceError:
            raise
        except PersistentBudgetExceeded as exc:
            raise ServiceError(
                "ARCHIVE_BUDGET_EXHAUSTED", "The server-owned archive budget is exhausted.", 429
            ) from exc
        except EvidenceUnavailableError as exc:
            raise ServiceError("GENUINE_EVIDENCE_UNAVAILABLE", str(exc), 422) from exc
        except UnsupportedCubeError as exc:
            raise ServiceError("UNSUPPORTED_FITS_LAYOUT", str(exc), 422) from exc
        except RangeExperimentError as exc:
            raise ServiceError("ARCHIVE_RANGE_FAILURE", str(exc), 502) from exc
        except (KeyError, TypeError, ValueError, MemoryError) as exc:
            raise ServiceError("DECODING_FAILURE", "The bounded cube sample could not be decoded.", 422) from exc
        finally:
            self._slot.release()
