"""Reusable experimental reader for bounded SPHEREx DR1 cube regions.

This package is intentionally separate from Cronoscope production pipelines.
It reuses the verified FITS offset/decoder and persistent-ledger components.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from astropy.io import fits

from research.dr1_cube_range.persistent_ledger import PersistentLedger
from research.dr1_cube_range.range_cube import (
    BoundedRangeClient,
    EXPECTED_HDU_NAMES,
    FITS_BLOCK,
    FitsLayoutError,
    HduLayout,
    ProductIdentity,
    decode_sample,
    inspect_layout,
    padded,
    sample_span,
)

MAX_REGION_SIDE = 32
CHANNEL_COUNT = 102
BLANK_CHANNELS = frozenset({51, 52})
ARRAY_NAMES = ("IMAGE", "NHITS", "FLAGS")


class CubeReaderError(RuntimeError):
    pass


class UnsupportedCubeError(CubeReaderError):
    pass


class EvidenceUnavailableError(CubeReaderError):
    pass


class BlankChannelError(CubeReaderError):
    pass


@dataclass(frozen=True)
class RegionRequest:
    channel: int
    x: int
    y: int
    width: int
    height: int
    allow_blank_channel: bool = False

    def validate(self, nx: int, ny: int, nz: int) -> None:
        if not 0 <= self.channel < CHANNEL_COUNT or self.channel >= nz:
            raise ValueError("channel must be in the inclusive range 0..101")
        if self.channel in BLANK_CHANNELS and not self.allow_blank_channel:
            raise BlankChannelError(
                f"channel {self.channel} is intentionally blank; set "
                "allow_blank_channel only for explicit blank-plane inspection"
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError("region dimensions must be positive")
        if self.width > MAX_REGION_SIDE or self.height > MAX_REGION_SIDE:
            raise ValueError("region dimensions cannot exceed 32x32")
        if self.x < 0 or self.y < 0 or self.x + self.width > nx or self.y + self.height > ny:
            raise ValueError("region lies outside the cube spatial bounds")


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
    sha256: str


class SavedEvidenceSource:
    """Read-only range source backed by the genuine DR1.3L response cache."""

    mode = "saved-genuine-evidence"
    network_requests = 0
    network_bytes = 0

    def __init__(self, evidence_root: Path | str) -> None:
        self.root = Path(evidence_root)
        result_path = self.root / "live_result.json"
        structure_path = self.root / "responses" / "verified_fits_structure.json"
        if not result_path.is_file() or not structure_path.is_file():
            raise EvidenceUnavailableError("saved evidence is incomplete")
        self.reference = json.loads(result_path.read_text())
        self.structure_reference = json.loads(structure_path.read_text())
        identity = self.reference["product_identity"]
        self.identity = ProductIdentity(
            identity["final_url"], int(identity["content_length"]),
            identity.get("last_modified"), identity.get("etag"),
        )
        self.segments: list[_Segment] = []
        for metadata_path in sorted((self.root / "responses").glob("request_*_bytes_*.json")):
            metadata = json.loads(metadata_path.read_text())
            data_path = metadata_path.with_suffix(".bin")
            data = data_path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if len(data) != metadata["content_length"] or digest != metadata["sha256"]:
                raise EvidenceUnavailableError(f"saved response failed integrity: {data_path}")
            self.segments.append(
                _Segment(int(metadata["start"]), int(metadata["end"]), data, digest)
            )
        self.cache_hits = 0

    def get(self, url: str, start: int, end: int) -> bytes:
        if url != self.identity.final_url:
            raise EvidenceUnavailableError("requested URL does not match saved product")
        for segment in self.segments:
            if segment.start <= start and end <= segment.end:
                self.cache_hits += 1
                left = start - segment.start
                return segment.data[left:left + (end - start + 1)]
        raise EvidenceUnavailableError(
            f"byte range {start}-{end} is absent from saved genuine evidence"
        )

    def reference_matches(self, request: RegionRequest, decoded: dict[str, np.ndarray]) -> bool:
        selection = self.reference["selection"]
        expected_key = (
            selection["channel_zero_based"], selection["x0"], selection["y0"],
            selection["width"], selection["height"],
        )
        actual_key = (request.channel, request.x, request.y, request.width, request.height)
        if actual_key != expected_key:
            return False
        return all(
            np.array_equal(
                values,
                np.asarray(self.reference["decoded"][name]["values"]),
                equal_nan=True,
            )
            for name, values in decoded.items()
        )


class InMemoryFitsSource:
    """Deterministic offline source for synthetic software tests."""

    mode = "synthetic-memory-fixture"
    network_requests = 0
    network_bytes = 0

    def __init__(self, raw: bytes, url: str = "fixture://cube.fits") -> None:
        self.raw = raw
        self.identity = ProductIdentity(url, len(raw), None, None)

    def get(self, url: str, start: int, end: int) -> bytes:
        if url != self.identity.final_url:
            raise EvidenceUnavailableError("fixture URL mismatch")
        if start < 0 or end >= len(self.raw):
            raise EvidenceUnavailableError("fixture range is unavailable")
        data = self.raw[start:end + 1]
        if len(data) != end - start + 1:
            raise EvidenceUnavailableError("fixture response is truncated")
        return data


class HttpRangeSource:
    """Future live source; requires an already initialized persistent ledger."""

    mode = "bounded-http-range"

    def __init__(
        self, url: str, ledger: PersistentLedger, artifact_dir: Path,
        *, expected_size: int,
    ) -> None:
        self.url = url
        self.ledger = ledger
        self.client = BoundedRangeClient(ledger, artifact_dir=artifact_dir)
        self.identity = self.client.head(url)
        if self.identity.content_length != expected_size:
            raise UnsupportedCubeError(
                f"product size {self.identity.content_length} does not match expected {expected_size}"
            )

    @property
    def network_requests(self) -> int:
        return self.ledger.snapshot(include_requests=False)["attempts"]

    @property
    def network_bytes(self) -> int:
        return self.ledger.snapshot(include_requests=False)["actual_received_bytes"]

    def get(self, url: str, start: int, end: int) -> bytes:
        return self.client.get(url, start, end)


class CubeReader:
    def __init__(
        self, source: RangeSource, *, strict_spherex_shape: bool = True,
        header_output_dir: Path | None = None,
    ) -> None:
        self.source = source
        self.url = source.identity.final_url
        self.strict_spherex_shape = strict_spherex_shape
        self.header_output_dir = header_output_dir
        self.layouts: list[HduLayout] | None = None
        self.by_name: dict[str, HduLayout] = {}
        self._channel_cache: dict[int, dict[str, Any]] | None = None

    def open(self) -> "CubeReader":
        try:
            layouts = inspect_layout(self.source, self.url)  # type: ignore[arg-type]
        except (FitsLayoutError, UnicodeError, KeyError, ValueError) as exc:
            raise UnsupportedCubeError(f"FITS structure rejected: {exc}") from exc
        if tuple(item.name for item in layouts) != EXPECTED_HDU_NAMES:
            raise UnsupportedCubeError("unexpected extension sequence")
        by_name = {item.name: item for item in layouts}
        if by_name["PRIMARY"].header.get("SIMPLE") is not True:
            raise UnsupportedCubeError("primary HDU is missing SIMPLE = T")
        if any(by_name[name].header.get("XTENSION", "").strip() != "IMAGE" for name in ARRAY_NAMES):
            raise UnsupportedCubeError("science extensions are not ordinary IMAGE HDUs")
        if any(
            by_name[name].header.get("XTENSION", "").strip() != "BINTABLE"
            for name in ("SPECTRAL_CHANNELS", "WCS-WAVE")
        ):
            raise UnsupportedCubeError("metadata extensions are not BINTABLE HDUs")
        for item in layouts:
            if bool(item.header.get("ZIMAGE", False)) or "ZCMPTYPE" in item.header:
                raise UnsupportedCubeError("compressed image HDUs are not supported")
        image, nhits, flags = (by_name[name] for name in ARRAY_NAMES)
        if image.bitpix != -32 or nhits.bitpix != 32 or flags.bitpix != 32:
            raise UnsupportedCubeError("IMAGE/NHITS/FLAGS data types are unsupported")
        if not (image.axes == nhits.axes == flags.axes) or len(image.axes) != 3:
            raise UnsupportedCubeError("science arrays are not aligned 3-D cubes")
        if image.axes[2] != CHANNEL_COUNT:
            raise UnsupportedCubeError("cube must contain 102 spectral channels")
        if self.strict_spherex_shape and image.axes[:2] != (512, 512):
            raise UnsupportedCubeError("official SPHEREx cube spatial shape must be 512x512")
        if self.header_output_dir is not None:
            self.header_output_dir.mkdir(parents=True, exist_ok=True)
            for item in layouts:
                path = self.header_output_dir / f"hdu_{item.index:02d}_{item.name}_header.bin"
                path.write_bytes(item.raw_header)
        self.layouts = layouts
        self.by_name = by_name
        return self

    def read_region(self, request: RegionRequest) -> dict[str, Any]:
        if self.layouts is None:
            self.open()
        started = time.perf_counter()
        image_layout = self.by_name["IMAGE"]
        nx, ny, nz = image_layout.axes
        request.validate(nx, ny, nz)
        decoded: dict[str, np.ndarray] = {}
        ranges: dict[str, dict[str, Any]] = {}
        for name in ARRAY_NAMES:
            layout = self.by_name[name]
            start, end, positions = sample_span(
                layout, request.channel, request.x, request.y,
                request.width, request.height,
            )
            raw = self.source.get(self.url, start, end)
            values = decode_sample(raw, layout, positions).reshape(
                request.height, request.width
            )
            decoded[name] = values
            ranges[name] = {
                "start": start, "end": end, "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        channel = self._channel_metadata(request.channel)
        reference_match = (
            isinstance(self.source, SavedEvidenceSource)
            and self.source.reference_matches(request, decoded)
        )
        validation = (
            "GENUINE_DR1_3L_REPLAY_MATCH" if reference_match
            else "STRUCTURALLY_DECODED_SOFTWARE_EVIDENCE"
        )
        result = {
            "schema_version": 1,
            "reader": "experimental-dr1-cube-reader",
            "source_mode": self.source.mode,
            "request": {
                "channel_zero_based": request.channel,
                "x": request.x, "y": request.y,
                "width": request.width, "height": request.height,
                "blank_channel": request.channel in BLANK_CHANNELS,
            },
            "arrays": {
                name: {
                    "dtype": str(values.dtype),
                    "values": _json_value(values),
                    "finite_count": int(np.isfinite(values).sum()),
                }
                for name, values in decoded.items()
            },
            "ranges": ranges,
            "science": {
                "image_unit": self.by_name["IMAGE"].header.get("BUNIT"),
                "channel": channel,
                "flags_semantics": "raw uninterpreted integer bitmap",
                "uncertainty": None,
            },
            "coordinates": self._coordinate_metadata(request),
            "provenance": {
                "product_url": self.url,
                "content_length": self.source.identity.content_length,
                "last_modified": self.source.identity.last_modified,
                "etag": self.source.identity.etag,
                "hdu_sequence": [item.name for item in self.layouts or []],
                "header_sha256": {
                    item.name: hashlib.sha256(item.raw_header).hexdigest()
                    for item in self.layouts or []
                },
            },
            "validation": {
                "classification": validation,
                "reference_match": bool(reference_match),
                "independent_photometric_calibration": False,
            },
            "resources": {
                "runtime_seconds": time.perf_counter() - started,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "network_requests": self.source.network_requests,
                "network_bytes": self.source.network_bytes,
                "cache_hits": getattr(self.source, "cache_hits", 0),
            },
            "limitations": [
                "Cube IMAGE is coadded surface brightness, not source photometry.",
                "NHITS is coverage context and no uncertainty array is invented.",
                "FLAGS are preserved without undocumented bit interpretation.",
                "The cube is not a time series and supports no variability or motion claim.",
            ],
        }
        return result

    def _channel_metadata(self, channel: int) -> dict[str, Any]:
        if self._channel_cache is not None:
            return self._channel_cache[channel]
        layout = self.by_name["SPECTRAL_CHANNELS"]
        raw = self.source.get(self.url, layout.data_start, layout.data_start + layout.data_bytes - 1)
        primary = fits.PrimaryHDU().header.tostring(endcard=True, padding=True).encode("ascii")
        payload = primary + layout.raw_header + raw + (b"\0" * (padded(len(raw)) - len(raw)))
        with fits.open(io.BytesIO(payload), memmap=False) as hdul:
            names = hdul[1].columns.names
            self._channel_cache = {
                index: {name: _json_value(row[name]) for name in names}
                for index, row in enumerate(hdul[1].data)
            }
        return self._channel_cache[channel]

    def _coordinate_metadata(self, request: RegionRequest) -> dict[str, Any]:
        header = self.by_name["IMAGE"].header
        keys = (
            "CTYPE1", "CTYPE2", "CUNIT1", "CUNIT2", "CRPIX1", "CRPIX2",
            "CRVAL1", "CRVAL2", "CDELT1", "CDELT2", "RADESYS",
        )
        return {
            "pixel_origin_zero_based": [request.x, request.y],
            "pixel_extent_zero_based_inclusive": [
                request.x, request.y,
                request.x + request.width - 1,
                request.y + request.height - 1,
            ],
            "fits_axis_order": ["x", "y", "spectral_channel"],
            "numpy_axis_order": ["spectral_channel", "y", "x"],
            "wcs_header": {key: _json_value(header[key]) for key in keys if key in header},
        }


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace").strip()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_result(path: Path, result: dict[str, Any]) -> int:
    encoded = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return len(encoded)
