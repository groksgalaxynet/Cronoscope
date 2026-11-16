"""Fail-closed HTTP byte-range and FITS-layout research utility.

This module is intentionally independent of Cronoscope's production image
retrieval and normalization paths.  It never permits an unbounded GET.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import resource
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS

from .persistent_ledger import PersistentLedger, Reservation

FITS_BLOCK = 2880
CARD_SIZE = 80
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_RANGE_REQUESTS = 20
EXPECTED_HDU_NAMES = ("PRIMARY", "IMAGE", "NHITS", "FLAGS", "SPECTRAL_CHANNELS", "WCS-WAVE")


class RangeExperimentError(RuntimeError):
    pass


class TransferBudgetExceeded(RangeExperimentError):
    pass


class RangeResponseError(RangeExperimentError):
    pass


class FitsLayoutError(RangeExperimentError):
    pass


@dataclass
class TransferLedger:
    max_bytes: int = DEFAULT_MAX_BYTES
    max_range_requests: int = DEFAULT_MAX_RANGE_REQUESTS
    body_bytes: int = 0
    http_requests: int = 0
    range_requests: int = 0

    def reserve_range(self, length: int) -> None:
        if length <= 0:
            raise ValueError("range length must be positive")
        if self.range_requests >= self.max_range_requests:
            raise TransferBudgetExceeded("range-request limit reached")
        if self.body_bytes + length > self.max_bytes:
            raise TransferBudgetExceeded("requested range would exceed transfer budget")
        self.range_requests += 1
        self.http_requests += 1

    def consume(self, length: int) -> None:
        if self.body_bytes + length > self.max_bytes:
            raise TransferBudgetExceeded("response exceeded transfer budget")
        self.body_bytes += length


@dataclass(frozen=True)
class ProductIdentity:
    final_url: str
    content_length: int
    last_modified: str | None
    etag: str | None


@dataclass
class RangeEvidence:
    start: int
    end: int
    status: int
    content_range: str
    content_length: int
    final_url: str
    redirects: list[str]
    sha256: str
    elapsed_seconds: float


@dataclass
class HduLayout:
    index: int
    name: str
    header_start: int
    header_length: int
    data_start: int
    data_bytes: int
    padded_data_bytes: int
    next_header_start: int
    bitpix: int
    naxis: int
    axes: tuple[int, ...]
    pcount: int
    gcount: int
    bscale: float
    bzero: float
    blank: int | None
    raw_header: bytes = field(repr=False)
    header: fits.Header = field(repr=False)

    def to_jsonable(self) -> dict[str, Any]:
        return {key: value for key, value in vars(self).items() if key not in {"raw_header", "header"}}


class BoundedRangeClient:
    def __init__(
        self, ledger: TransferLedger | PersistentLedger,
        session: requests.Session | None = None, timeout: float = 30.0,
        artifact_dir: Path | None = None,
    ) -> None:
        self.ledger = ledger
        self.session = session or requests.Session()
        self.timeout = timeout
        self.artifact_dir = artifact_dir
        self.identity: ProductIdentity | None = None
        self.ranges: list[RangeEvidence] = []

    def head(self, url: str) -> ProductIdentity:
        reservation: Reservation | None = None
        if isinstance(self.ledger, PersistentLedger):
            reservation = self.ledger.reserve_request(
                method="HEAD", url=url, planned_bytes=0
            )
        else:
            self.ledger.http_requests += 1
        response = None
        try:
            response = self.session.head(url, allow_redirects=True, timeout=self.timeout)
            response.raise_for_status()
            length = int(response.headers["Content-Length"])
            if length <= 0:
                raise RangeResponseError("HEAD returned invalid Content-Length")
            if response.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise RangeResponseError("server did not advertise byte ranges")
            self.identity = ProductIdentity(response.url, length, response.headers.get("Last-Modified"), response.headers.get("ETag"))
            if self.artifact_dir is not None and reservation is not None:
                _write_json_durable(
                    self.artifact_dir / f"request_{reservation.sequence:03d}_HEAD.json",
                    {
                        "request_id": reservation.request_id,
                        "sequence": reservation.sequence,
                        "method": "HEAD",
                        "status": response.status_code,
                        "final_url": response.url,
                        "redirects": [item.url for item in response.history],
                        "content_length": length,
                        "accept_ranges": response.headers.get("Accept-Ranges"),
                        "last_modified": response.headers.get("Last-Modified"),
                        "etag": response.headers.get("ETag"),
                    },
                )
            if reservation is not None:
                self.ledger.finish_request(
                    reservation, state="completed", http_status=response.status_code
                )
            return self.identity
        except Exception as exc:
            if reservation is not None:
                self.ledger.finish_request(
                    reservation,
                    state="failed",
                    http_status=None if response is None else response.status_code,
                    error=f"{type(exc).__name__}: {exc}",
                )
            raise
        finally:
            if response is not None:
                response.close()

    def get(self, url: str, start: int, end: int) -> bytes:
        if start < 0 or end < start:
            raise ValueError("invalid byte range")
        expected = end - start + 1
        reservation: Reservation | None = None
        if isinstance(self.ledger, PersistentLedger):
            reservation = self.ledger.reserve_request(
                method="GET", url=url, planned_bytes=expected,
                range_start=start, range_end=end,
            )
        else:
            self.ledger.reserve_range(expected)
        started = time.perf_counter()
        response = None
        finalized = False
        try:
            response = self.session.get(
                url, headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
                allow_redirects=True, stream=True, timeout=self.timeout,
            )
            if response.status_code == 200:
                response.close()
                raise RangeResponseError("server ignored Range and returned HTTP 200; body was not consumed")
            if response.status_code != 206:
                response.close()
                raise RangeResponseError(f"expected HTTP 206, received {response.status_code}")
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if not match:
                raise RangeResponseError("missing or malformed Content-Range")
            actual_start, actual_end, total = map(int, match.groups())
            if (actual_start, actual_end) != (start, end):
                raise RangeResponseError("Content-Range does not match request")
            if self.identity is not None:
                if total != self.identity.content_length or response.url != self.identity.final_url:
                    raise RangeResponseError("product identity changed between requests")
                for key, expected_identity in (("Last-Modified", self.identity.last_modified), ("ETag", self.identity.etag)):
                    actual_identity = response.headers.get(key)
                    if expected_identity and actual_identity and expected_identity != actual_identity:
                        raise RangeResponseError(f"product {key} changed between requests")
            declared = int(response.headers.get("Content-Length", "-1"))
            if declared != expected:
                raise RangeResponseError("range Content-Length is incorrect")
            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_content(chunk_size=min(65536, expected)):
                if not chunk:
                    continue
                received += len(chunk)
                if reservation is not None:
                    self.ledger.record_received(reservation, len(chunk))
                else:
                    self.ledger.consume(len(chunk))
                if received > expected:
                    raise RangeResponseError("range response exceeded requested length")
                chunks.append(chunk)
            if received != expected:
                raise RangeResponseError("range response was truncated")
            data = b"".join(chunks)
            evidence = RangeEvidence(
                start, end, response.status_code, response.headers["Content-Range"], received, response.url,
                [item.url for item in response.history], hashlib.sha256(data).hexdigest(), time.perf_counter() - started,
            )
            if self.artifact_dir is not None and reservation is not None:
                stem = f"request_{reservation.sequence:03d}_bytes_{start}_{end}"
                _write_bytes_durable(self.artifact_dir / f"{stem}.bin", data)
                _write_json_durable(
                    self.artifact_dir / f"{stem}.json",
                    {
                        "request_id": reservation.request_id,
                        "sequence": reservation.sequence,
                        **vars(evidence),
                    },
                )
            self.ranges.append(evidence)
            if reservation is not None:
                self.ledger.finish_request(
                    reservation, state="completed", http_status=response.status_code,
                    content_range=response.headers["Content-Range"],
                )
                finalized = True
            return data
        except Exception as exc:
            if reservation is not None and not finalized:
                self.ledger.finish_request(
                    reservation, state="failed",
                    http_status=None if response is None else response.status_code,
                    content_range=None if response is None else response.headers.get("Content-Range"),
                    error=f"{type(exc).__name__}: {exc}",
                )
                finalized = True
            raise
        finally:
            if response is not None:
                response.close()


def padded(length: int, block: int = FITS_BLOCK) -> int:
    if length < 0:
        raise ValueError("length cannot be negative")
    return ((length + block - 1) // block) * block


def parse_header(raw: bytes) -> tuple[fits.Header, int, bytes]:
    if len(raw) % FITS_BLOCK:
        raise FitsLayoutError("header bytes are not FITS-block aligned")
    end_offset = None
    for offset in range(0, len(raw), CARD_SIZE):
        card = raw[offset:offset + CARD_SIZE]
        if len(card) < CARD_SIZE:
            break
        if card[:8].decode("ascii", errors="strict").strip() == "END":
            end_offset = offset + CARD_SIZE
            break
    if end_offset is None:
        raise FitsLayoutError("FITS header has no END card")
    length = padded(end_offset)
    try:
        header = fits.Header.fromstring(raw[:length].decode("ascii"), sep="")
    except Exception as exc:
        raise FitsLayoutError(f"Astropy rejected FITS header: {exc}") from exc
    return header, length, raw[:length]


def data_size(header: fits.Header) -> int:
    bitpix = int(header.get("BITPIX", 0))
    naxis = int(header.get("NAXIS", 0))
    if naxis == 0:
        return 0
    if abs(bitpix) not in {8, 16, 32, 64}:
        raise FitsLayoutError(f"unsupported BITPIX {bitpix}")
    axes = [int(header[f"NAXIS{i}"]) for i in range(1, naxis + 1)]
    pcount = int(header.get("PCOUNT", 0)); gcount = int(header.get("GCOUNT", 1))
    return (abs(bitpix) // 8) * gcount * (math.prod(axes) + pcount)


def read_header(client: BoundedRangeClient, url: str, start: int) -> tuple[fits.Header, int, bytes]:
    if client.identity is None:
        raise FitsLayoutError("HEAD identity must be established first")
    # Read exactly one FITS block at a time so a short header request never
    # spills across the verified header boundary into array data.
    initial = min(FITS_BLOCK, client.identity.content_length - start)
    initial -= initial % FITS_BLOCK
    if initial <= 0:
        raise FitsLayoutError("no complete FITS block remains for header")
    blocks: list[bytes] = [client.get(url, start, start + initial - 1)]
    while True:
        joined = b"".join(blocks)
        try:
            return parse_header(joined)
        except FitsLayoutError as exc:
            if "no END card" not in str(exc):
                raise
        block_start = start + len(joined)
        if block_start + FITS_BLOCK > client.identity.content_length:
            raise FitsLayoutError("truncated FITS header at end of product")
        blocks.append(client.get(url, block_start, block_start + FITS_BLOCK - 1))


def inspect_layout(client: BoundedRangeClient, url: str) -> list[HduLayout]:
    if client.identity is None:
        raise FitsLayoutError("HEAD identity must be established first")
    layouts: list[HduLayout] = []
    offset = 0
    for index in range(16):
        if offset >= client.identity.content_length:
            break
        header, header_length, raw_header = read_header(client, url, offset)
        size = data_size(header); padded_size = padded(size)
        name = "PRIMARY" if index == 0 else str(header.get("EXTNAME", f"HDU{index}"))
        layout = HduLayout(
            index=index, name=name, header_start=offset, header_length=header_length,
            data_start=offset + header_length, data_bytes=size, padded_data_bytes=padded_size,
            next_header_start=offset + header_length + padded_size, bitpix=int(header.get("BITPIX", 0)),
            naxis=int(header.get("NAXIS", 0)), axes=tuple(int(header[f"NAXIS{i}"]) for i in range(1, int(header.get("NAXIS", 0)) + 1)),
            pcount=int(header.get("PCOUNT", 0)), gcount=int(header.get("GCOUNT", 1)),
            bscale=float(header.get("BSCALE", 1.0)), bzero=float(header.get("BZERO", 0.0)),
            blank=None if header.get("BLANK") is None else int(header["BLANK"]), raw_header=raw_header, header=header,
        )
        layouts.append(layout); offset = layout.next_header_start
    if offset != client.identity.content_length:
        raise FitsLayoutError(f"calculated FITS length {offset} does not match Content-Length {client.identity.content_length}")
    names = tuple(item.name for item in layouts)
    if names != EXPECTED_HDU_NAMES:
        raise FitsLayoutError(f"unexpected HDU sequence: {names}")
    return layouts


def numpy_dtype(bitpix: int) -> np.dtype:
    mapping = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}
    try:
        return np.dtype(mapping[bitpix])
    except KeyError as exc:
        raise FitsLayoutError(f"unsupported BITPIX {bitpix}") from exc


def sample_span(layout: HduLayout, channel: int, x0: int, y0: int, width: int, height: int) -> tuple[int, int, list[int]]:
    if layout.naxis != 3 or len(layout.axes) != 3:
        raise FitsLayoutError(f"{layout.name} is not a 3-D array")
    nx, ny, nz = layout.axes
    if not (0 <= channel < nz and 0 <= x0 < nx and 0 <= y0 < ny and width > 0 and height > 0 and x0 + width <= nx and y0 + height <= ny):
        raise ValueError("sample is outside array bounds")
    itemsize = abs(layout.bitpix) // 8
    first = (channel * ny * nx) + (y0 * nx) + x0
    last = (channel * ny * nx) + ((y0 + height - 1) * nx) + (x0 + width - 1)
    positions = [((y * nx + x) - (y0 * nx + x0)) for y in range(y0, y0 + height) for x in range(x0, x0 + width)]
    return layout.data_start + first * itemsize, layout.data_start + (last + 1) * itemsize - 1, positions


def decode_sample(raw: bytes, layout: HduLayout, positions: list[int]) -> np.ndarray:
    dtype = numpy_dtype(layout.bitpix)
    if len(raw) % dtype.itemsize:
        raise FitsLayoutError("sample byte count is not item-aligned")
    values = np.frombuffer(raw, dtype=dtype)
    if max(positions, default=-1) >= len(values):
        raise FitsLayoutError("sample positions exceed returned range")
    selected = values[positions].reshape(-1).copy()
    if layout.blank is not None and layout.bitpix > 0:
        selected = selected.astype(float)
        selected[selected == layout.blank] = np.nan
    if layout.bscale != 1.0 or layout.bzero != 0.0:
        selected = selected.astype(float) * layout.bscale + layout.bzero
    return selected


def write_sparse_equivalent(path: Path, total_length: int, layouts: list[HduLayout], ranges: list[tuple[int, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.truncate(total_length)
        for layout in layouts:
            handle.seek(layout.header_start); handle.write(layout.raw_header)
        for offset, data in ranges:
            handle.seek(offset); handle.write(data)


def _write_bytes_durable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_json_durable(path: Path, value: Any) -> None:
    _write_bytes_durable(
        path, (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    )


def run_experiment(
    url: str, evidence_path: Path, sparse_path: Path, ra_deg: float,
    dec_deg: float, ledger: PersistentLedger, artifact_dir: Path,
) -> dict[str, Any]:
    client = BoundedRangeClient(ledger, artifact_dir=artifact_dir)
    started = time.perf_counter(); identity = client.head(url)
    layouts = inspect_layout(client, url)
    by_name = {item.name: item for item in layouts}
    header_evidence = []
    for layout in layouts:
        header_path = artifact_dir / f"hdu_{layout.index:02d}_{layout.name}_header.bin"
        _write_bytes_durable(header_path, layout.raw_header)
        header_evidence.append({
            **layout.to_jsonable(),
            "header_file": header_path.name,
            "header_sha256": hashlib.sha256(layout.raw_header).hexdigest(),
        })
    _write_json_durable(
        artifact_dir / "verified_fits_structure.json",
        {
            "product_identity": vars(identity),
            "expected_hdu_names": list(EXPECTED_HDU_NAMES),
            "calculated_product_length": layouts[-1].next_header_start,
            "hdu_layouts": header_evidence,
        },
    )

    # Fetch both small tables in full; they are required for independent Astropy parsing.
    sparse_ranges: list[tuple[int, bytes]] = []
    for name in ("SPECTRAL_CHANNELS", "WCS-WAVE"):
        layout = by_name[name]
        raw = client.get(url, layout.data_start, layout.data_start + layout.data_bytes - 1)
        sparse_ranges.append((layout.data_start, raw))

    # -TAB WCS requires its companion HDU.  Construct the sparse logical FITS
    # before any science-array request and give Astropy the complete HDUList.
    write_sparse_equivalent(sparse_path, identity.content_length, layouts, sparse_ranges)
    with fits.open(sparse_path, memmap=True, lazy_load_hdus=True) as hdul:
        celestial = WCS(hdul["IMAGE"].header, fobj=hdul).celestial
        px, py = celestial.world_to_pixel_values(ra_deg, dec_deg)
    if not np.isfinite(px) or not np.isfinite(py):
        raise FitsLayoutError("target coordinate did not map to a finite pixel")
    x0 = max(0, min(508, int(math.floor(px)) - 1)); y0 = max(0, min(508, int(math.floor(py)) - 1))
    width = height = 4

    # Channel 20 (zero-based) is intentionally fixed before data retrieval and
    # is neither of the excluded channels 51/52. Its authoritative wavelength
    # metadata is preserved from SPECTRAL_CHANNELS below.
    selected_channel = 20
    decoded: dict[str, np.ndarray] = {}; sample_meta: dict[str, Any] = {}
    candidate_ranges: list[tuple[int, bytes]] = []
    for name in ("IMAGE", "NHITS", "FLAGS"):
        layout = by_name[name]
        start, end, positions = sample_span(layout, selected_channel, x0, y0, width, height)
        raw = client.get(url, start, end)
        values = decode_sample(raw, layout, positions)
        decoded[name] = values.reshape(height, width)
        sample_meta[name] = {
            "start": start, "end": end, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        candidate_ranges.append((start, raw))
    if not np.any(np.isfinite(decoded["IMAGE"])) or not np.any(decoded["NHITS"] > 0):
        raise FitsLayoutError("fixed channel 20 sample had no finite IMAGE pixel with NHITS > 0")
    sparse_ranges.extend(candidate_ranges)

    write_sparse_equivalent(sparse_path, identity.content_length, layouts, sparse_ranges)
    with fits.open(sparse_path, memmap=True, do_not_scale_image_data=False) as hdul:
        independent = {name: np.asarray(hdul[name].data[selected_channel, y0:y0 + height, x0:x0 + width]).copy() for name in ("IMAGE", "NHITS", "FLAGS")}
        channel_table = hdul["SPECTRAL_CHANNELS"].data[selected_channel]
        table_names = list(hdul["SPECTRAL_CHANNELS"].columns.names)
        wave_names = list(hdul["WCS-WAVE"].columns.names)
    comparisons = {name: bool(np.array_equal(decoded[name], independent[name], equal_nan=True)) for name in decoded}
    if not all(comparisons.values()):
        raise FitsLayoutError("independent Astropy sparse-FITS decoding disagreed")

    peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "schema_version": 1, "classification": "VERIFIED", "product_url": url,
        "product_identity": vars(identity), "ledger": ledger.snapshot(),
        "hdu_layouts": [item.to_jsonable() for item in layouts],
        "range_evidence": [vars(item) for item in client.ranges],
        "selection": {"channel_zero_based": selected_channel, "x0": x0, "y0": y0, "width": width, "height": height,
                      "target_ra_deg": ra_deg, "target_dec_deg": dec_deg, "sample_ranges": sample_meta},
        "decoded": {name: {"dtype": str(values.dtype), "values": _json_value(values), "finite_count": int(np.isfinite(values).sum())} for name, values in decoded.items()},
        "independent_validation": {"method": "Astropy opened a sparse, byte-identical FITS representation containing genuine headers, tables, and requested data ranges", "matches": comparisons, "table_columns": table_names, "wcs_wave_columns": wave_names, "selected_channel_row": {name: _json_scalar(channel_table[name]) for name in table_names}},
        "resource": {"peak_rss_kib": peak_kib, "runtime_seconds": time.perf_counter() - started, "sparse_logical_bytes": sparse_path.stat().st_size, "sparse_allocated_bytes": sparse_path.stat().st_blocks * 512},
        "limitations": ["Sample validates byte decoding and alignment, not source photometry.", "Cube is a multi-epoch coadd, not a time-domain observation.", "Sparse validation uses the same authoritative remote bytes with an independent FITS reader."],
    }
    _write_json_durable(evidence_path, result)
    return result


def run_recovery_experiment(
    url: str, evidence_path: Path, sparse_path: Path, *, prior_range_attempts: int = 9,
) -> dict[str, Any]:
    """Complete a fixed-pixel experiment after the bounded -TAB WCS stop.

    The first attempt stopped after six headers, one consistency read, and two
    small-table reads.  This path is capped at the eleven remaining attempts;
    in practice it uses ten (six headers, one tiny probe, three aligned spans).
    """
    raise RangeExperimentError(
        "legacy in-memory recovery mode is retired; initialize and use a "
        "persistent experiment ledger for any separately authorized run"
    )
    if prior_range_attempts != 9:  # pragma: no cover - retained historical code
        raise ValueError("the documented recovery path requires exactly 9 prior attempts")
    ledger = TransferLedger(max_range_requests=DEFAULT_MAX_RANGE_REQUESTS - prior_range_attempts)
    client = BoundedRangeClient(ledger)
    started = time.perf_counter(); identity = client.head(url)
    layouts = inspect_layout(client, url); by_name = {item.name: item for item in layouts}

    selected_channel = 20; x0 = 254; y0 = 254; width = height = 4
    decoded: dict[str, np.ndarray] = {}; sample_meta: dict[str, Any] = {}
    sparse_ranges: list[tuple[int, bytes]] = []
    image_layout = by_name["IMAGE"]
    image_start, _, _ = sample_span(image_layout, selected_channel, x0, y0, width, height)
    image_itemsize = abs(image_layout.bitpix) // 8
    tiny_raw = client.get(url, image_start, image_start + image_itemsize - 1)
    tiny_value = decode_sample(tiny_raw, image_layout, [0])[0]

    for name in ("IMAGE", "NHITS", "FLAGS"):
        layout = by_name[name]
        start, end, positions = sample_span(layout, selected_channel, x0, y0, width, height)
        raw = client.get(url, start, end); values = decode_sample(raw, layout, positions)
        if name == "IMAGE" and not np.array_equal(np.asarray([tiny_value]), values[:1], equal_nan=True):
            raise FitsLayoutError("IMAGE tiny probe disagreed with expanded sample")
        decoded[name] = values.reshape(height, width)
        sample_meta[name] = {"start": start, "end": end, "bytes": len(raw)}
        sparse_ranges.append((start, raw))
    if not np.any(np.isfinite(decoded["IMAGE"])) or not np.any(decoded["NHITS"] > 0):
        raise FitsLayoutError("fixed channel 20 central sample had no finite IMAGE pixel with NHITS > 0")

    write_sparse_equivalent(sparse_path, identity.content_length, layouts, sparse_ranges)
    with fits.open(sparse_path, memmap=True, lazy_load_hdus=True, do_not_scale_image_data=False) as hdul:
        independent = {
            name: np.asarray(hdul[name].data[selected_channel, y0:y0 + height, x0:x0 + width]).copy()
            for name in ("IMAGE", "NHITS", "FLAGS")
        }
    comparisons = {name: bool(np.array_equal(decoded[name], independent[name], equal_nan=True)) for name in decoded}
    if not all(comparisons.values()):
        raise FitsLayoutError("independent Astropy sparse-FITS decoding disagreed")

    # Exact first-attempt body bytes are reconstructible from its deterministic
    # request plan and the genuine table sizes now present in the headers.
    prior_body_bytes = 7 * (2 * FITS_BLOCK) + by_name["SPECTRAL_CHANNELS"].data_bytes + by_name["WCS-WAVE"].data_bytes
    cumulative_range_attempts = prior_range_attempts + ledger.range_requests
    cumulative_http_requests = cumulative_range_attempts + 2  # one HEAD per bounded run
    cumulative_body_bytes = prior_body_bytes + ledger.body_bytes
    if cumulative_range_attempts > DEFAULT_MAX_RANGE_REQUESTS or cumulative_body_bytes > DEFAULT_MAX_BYTES:
        raise TransferBudgetExceeded("cumulative recovery accounting exceeded a hard limit")

    peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result = {
        "schema_version": 1, "classification": "VERIFIED", "product_url": url,
        "product_identity": vars(identity),
        "ledger": vars(ledger),
        "cumulative_ledger": {
            "body_bytes": cumulative_body_bytes, "http_requests": cumulative_http_requests,
            "range_requests": cumulative_range_attempts, "max_bytes": DEFAULT_MAX_BYTES,
            "max_range_requests": DEFAULT_MAX_RANGE_REQUESTS,
        },
        "prior_safe_stop": {
            "range_requests": prior_range_attempts, "body_bytes": prior_body_bytes,
            "reason": "Astropy celestial WCS construction required an HDUList for -TAB coordinates; no science-array bytes had been requested",
        },
        "hdu_layouts": [item.to_jsonable() for item in layouts],
        "range_evidence": [vars(item) for item in client.ranges],
        "selection": {
            "channel_zero_based": selected_channel, "x0": x0, "y0": y0,
            "width": width, "height": height, "coordinate_basis": "fixed central FITS pixels",
            "tiny_image_probe": {"start": image_start, "end": image_start + image_itemsize - 1, "bytes": image_itemsize},
            "sample_ranges": sample_meta,
        },
        "decoded": {
            name: {"dtype": str(values.dtype), "values": _json_value(values), "finite_count": int(np.isfinite(values).sum())}
            for name, values in decoded.items()
        },
        "independent_validation": {
            "method": "Astropy independently opened a sparse logical FITS file containing genuine remote headers and the exact retrieved IMAGE/NHITS/FLAGS byte spans",
            "matches": comparisons,
        },
        "resource": {
            "peak_rss_kib": peak_kib, "runtime_seconds": time.perf_counter() - started,
            "sparse_logical_bytes": sparse_path.stat().st_size,
            "sparse_allocated_bytes": sparse_path.stat().st_blocks * 512,
        },
        "limitations": [
            "The sample validates storage, indexing, and decoding; it is not an external photometric calibration check.",
            "Fixed FITS pixels were used because celestial -TAB WCS requires the complete HDU context.",
            "The cube is a multi-epoch coadd and does not establish time-domain variability.",
        ],
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace").strip()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _json_scalar(value: Any) -> Any:
    return _json_value(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--sparse", type=Path)
    parser.add_argument("--ra", type=float)
    parser.add_argument("--dec", type=float)
    parser.add_argument("--ledger-db", required=True, type=Path)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--initialize-ledger", action="store_true")
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_RANGE_REQUESTS)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    if args.initialize_ledger:
        ledger = PersistentLedger.initialize(
            args.ledger_db, args.experiment_id,
            max_requests=args.max_requests, max_bytes=args.max_bytes,
        )
    else:
        ledger = PersistentLedger(args.ledger_db, args.experiment_id)
    before = ledger.snapshot()
    print(json.dumps({"ledger_before_execution": before}, indent=2), flush=True)
    if args.initialize_only:
        return 0
    missing = [
        name for name in ("url", "evidence", "sparse", "ra", "dec")
        if getattr(args, name) is None
    ]
    if missing:
        parser.error(
            "experiment execution requires: " + ", ".join(f"--{name}" for name in missing)
        )
    if args.artifact_dir is None:
        parser.error("experiment execution requires: --artifact-dir")
    result = run_experiment(
        args.url, args.evidence, args.sparse, args.ra, args.dec, ledger,
        args.artifact_dir,
    )
    print(json.dumps({"classification": result["classification"], "ledger": result["ledger"], "selection": result["selection"], "resource": result["resource"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
